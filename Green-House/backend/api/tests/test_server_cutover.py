from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rest_framework.test import APIClient

from api.models import (
    AMPCRecommendation,
    AMPCSchedulerState,
    ControlState,
    Device,
    DeviceCommand,
    EstimationCycle,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
    SensorData,
)
from api.ampc import run_auto_recommendation
from api.ampc_scheduler import run_due_once
from api.estimation import ensure_estimation_for_reading


@override_settings(INGEST_DEVICE_TOKEN='test-ingest-token')
class GreenHouseServerCutoverTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='owner', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')
        self.greenhouse = Greenhouse.objects.create(owner=self.user, name='GH-A')
        self.other_greenhouse = Greenhouse.objects.create(owner=self.other_user, name='GH-B')
        self.run = ExperimentRun.objects.create(
            name='Live run',
            run_type=ExperimentRun.RunType.LIVE,
            status=ExperimentRun.Status.RUNNING,
            greenhouse=self.greenhouse,
        )
        GreenhouseControlProfile.objects.create(
            greenhouse=self.greenhouse,
            target_low=55.0,
            target_high=65.0,
            pump_max_seconds=300.0,
            actuator_enabled=False,
        )
        self.client = APIClient(HTTP_HOST='127.0.0.1')
        self.client.force_authenticate(self.user)

    def test_legacy_run_and_control_profile_endpoints_are_owner_scoped(self):
        response = self.client.get('/api/runs/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()], [self.run.id])

        response = self.client.get(f'/api/greenhouses/{self.greenhouse.id}/control-profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['greenhouse_id'], self.greenhouse.id)

        response = self.client.get(f'/api/greenhouses/{self.other_greenhouse.id}/control-profile/')
        self.assertEqual(response.status_code, 404)

    def test_ingest_samples_writes_api_estimationcycle_for_run_and_greenhouse(self):
        response = self.client.post(
            '/api/ingest/samples/',
            {
                'run_id': self.run.id,
                'timestamp': timezone.now().isoformat(),
                'soil_moisture': 60.0,
                'temperature': 28.0,
                'humidity': 70.0,
                'light': 10000.0,
                'drip': 0.0,
                'mist': 0.0,
                'fan': 0.0,
            },
            format='json',
            HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
        )

        self.assertEqual(response.status_code, 201)
        cycle = EstimationCycle.objects.get(id=response.json()['id'])
        self.assertEqual(cycle.run_id, self.run.id)
        self.assertEqual(cycle.greenhouse_id, self.greenhouse.id)
        self.assertEqual(cycle.source_type, 'live')
        self.assertTrue(cycle.ingest_dedupe_key.startswith(f'live|{self.run.id}|'))

    def test_greenhouse_ampc_recommendation_persists_scoped_audit(self):
        self.assertTrue(Path(settings.ARX_MODEL_PATH).exists(), settings.ARX_MODEL_PATH)
        now = timezone.now()
        for index in range(3):
            self.client.post(
                '/api/ingest/samples/',
                {
                    'run_id': self.run.id,
                    'timestamp': (now - timedelta(minutes=(2 - index) * 5)).isoformat(),
                    'soil_moisture': 60.0 + index,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    'drip': 0.0,
                    'mist': 0.0,
                    'fan': 0.0,
                },
                format='json',
                HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
            )

        response = self.client.post(f'/api/greenhouses/{self.greenhouse.id}/ampc/recommendations/', {}, format='json')
        self.assertIn(response.status_code, {200, 202})

        audit = AMPCRecommendation.objects.get(id=response.json()['id'])
        self.assertEqual(audit.greenhouse_id, self.greenhouse.id)
        self.assertEqual(audit.run_id, self.run.id)
        self.assertNotEqual(audit.safety_status, 'model_error')
        self.assertNotIn('artifact not found', audit.reason.lower())
        self.assertGreater(len(audit.predicted_soil_moisture), 0)
        self.assertFalse(audit.command_created)

    def test_reading_ingest_does_not_run_ampc_even_when_auto(self):
        ControlState.objects.update_or_create(
            singleton_key='main',
            defaults={'mode': ControlState.Mode.AUTO},
        )
        Device.objects.create(
            greenhouse=self.greenhouse,
            name='ESP32 Main',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            status=Device.DeviceStatus.ONLINE,
        )

        response = self.client.post(
            '/api/ingest/readings/',
            {
                'recorded_at': timezone.now().isoformat(),
                'soil_moisture': 60.0,
                'temperature': 28.0,
                'humidity': 70.0,
                'light': 10000.0,
                'auto_mode': True,
            },
            format='json',
            HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['recommendation_id'])
        self.assertEqual(AMPCRecommendation.objects.count(), 0)
        self.assertEqual(DeviceCommand.objects.count(), 0)

    def test_ampc_error_does_not_queue_pump_command(self):
        profile = GreenhouseControlProfile.objects.get(greenhouse=self.greenhouse)
        profile.actuator_enabled = True
        profile.save(update_fields=['actuator_enabled', 'updated_at'])
        ControlState.objects.update_or_create(
            singleton_key=f'greenhouse:{self.greenhouse.id}'[:20],
            defaults={'greenhouse': self.greenhouse, 'mode': ControlState.Mode.AUTO},
        )
        Device.objects.create(
            greenhouse=self.greenhouse,
            name='Pump',
            code='pump-test',
            device_type=Device.DeviceType.PUMP,
            status=Device.DeviceStatus.ONLINE,
        )

        response = self.client.post(
            f'/api/greenhouses/{self.greenhouse.id}/ampc/recommendations/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, 202)
        audit = AMPCRecommendation.objects.get(id=response.json()['id'])
        self.assertEqual(audit.safety_status, 'model_error')
        self.assertEqual(audit.reason, 'missing_estimation')
        self.assertFalse(audit.command_created)
        self.assertEqual(audit.actuator_status, AMPCRecommendation.ActuatorStatus.UNSAFE_SKIPPED)
        self.assertEqual(DeviceCommand.objects.count(), 0)

    def test_ampc_scheduler_start_persists_state_and_runs_once(self):
        now = timezone.now()
        for index in range(3):
            self.client.post(
                '/api/ingest/samples/',
                {
                    'run_id': self.run.id,
                    'timestamp': (now - timedelta(minutes=(2 - index) * 5)).isoformat(),
                    'soil_moisture': 60.0 + index,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    'drip': 0.0,
                    'mist': 0.0,
                    'fan': 0.0,
                },
                format='json',
                HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
            )

        response = self.client.post('/api/control/ampc-scheduler/start/', {}, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['is_enabled'])
        self.assertEqual(payload['greenhouse_id'], self.greenhouse.id)
        self.assertIsNotNone(payload['last_run_at'])
        self.assertIsNotNone(payload['next_run_at'])
        self.assertTrue(AMPCRecommendation.objects.filter(greenhouse=self.greenhouse).exists())

    def test_ampc_scheduler_stop_persists_disabled_state(self):
        AMPCSchedulerState.objects.create(
            singleton_key=f'greenhouse:{self.greenhouse.id}',
            greenhouse=self.greenhouse,
            is_enabled=True,
            next_run_at=timezone.now(),
        )

        response = self.client.post('/api/control/ampc-scheduler/stop/', {}, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['is_enabled'])
        self.assertIsNone(payload['next_run_at'])

    def test_auto_settings_updates_greenhouse_profile_used_by_ampc(self):
        response = self.client.patch(
            '/api/auto-settings/',
            {
                'target_low': 57.0,
                'target_high': 66.0,
                'weight_daily': 7.5,
                'stale_after_seconds': 900,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['target_low'], 57.0)
        self.assertEqual(payload['weight_daily'], 7.5)
        profile = GreenhouseControlProfile.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(profile.target_low, 57.0)
        self.assertEqual(profile.target_high, 66.0)
        self.assertEqual(profile.cost_daily_cap_excess, 7.5)
        self.assertEqual(profile.safety_stale_after_seconds, 900)

    def test_forecast_does_not_fallback_to_other_greenhouse_recommendation(self):
        AMPCRecommendation.objects.create(
            greenhouse=self.other_greenhouse,
            pump_seconds=123.0,
            step_seconds=300,
            safety_status='safe',
            reason='other_greenhouse_only',
            predicted_soil_moisture=[60.0],
            target_band={'low': 55.0, 'high': 65.0},
        )

        response = self.client.get('/api/forecast/')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['recommendation'])

    def test_ampc_scheduler_recovers_stale_execution_lease(self):
        state = AMPCSchedulerState.objects.create(
            singleton_key='main',
            greenhouse=self.greenhouse,
            is_enabled=True,
            is_executing=True,
            interval_seconds=300,
            next_run_at=timezone.now() - timedelta(minutes=30),
        )
        stale_at = timezone.now() - timedelta(minutes=20)
        AMPCSchedulerState.objects.filter(pk=state.pk).update(updated_at=stale_at)

        with patch(
            'api.ampc_scheduler.run_auto_recommendation',
            return_value=SimpleNamespace(safety_status='safe', reason=''),
        ) as recommendation:
            recovered = run_due_once(force=True)

        recommendation.assert_called_once_with(
            create_command_if_auto=True,
            greenhouse_id=self.greenhouse.id,
        )
        self.assertFalse(recovered.is_executing)
        self.assertEqual(recovered.last_status, 'safe')
        self.assertEqual(recovered.last_error, '')
        self.assertIsNotNone(recovered.next_run_at)

    def test_live_kalman_trusts_valid_sensor_when_arx_prior_is_far_off(self):
        previous_ts = timezone.now() - timedelta(minutes=5)
        EstimationCycle.objects.create(
            sample_ts=previous_ts,
            cycle_index=10,
            greenhouse=self.greenhouse,
            slice_type='online',
            source_type='live',
            validation_status='valid',
            preprocess_status=EstimationCycle.PreprocessStatus.VALID,
            cycle_status=EstimationCycle.CycleStatus.OK,
            adaptive_status=EstimationCycle.AdaptiveStatus.R_UPDATED,
            raw_soil_moisture=60.0,
            raw_temperature=28.0,
            raw_humidity=70.0,
            raw_light=10000.0,
            raw_drip=0.0,
            raw_mist=0.0,
            raw_fan=0.0,
            arx_predicted=40.0,
            kf_x_prior=40.0,
            kf_P_prior=1.0,
            kf_innovation=20.0,
            kf_R=25.0,
            kf_K=0.02,
            kf_x_posterior=40.0,
            kf_P_posterior=0.6,
            ingest_dedupe_key='stale-bad-kf-state',
        )
        reading = SensorData.objects.create(
            greenhouse=self.greenhouse,
            recorded_at=timezone.now(),
            soil_moisture=60.0,
            temperature=28.0,
            humidity=70.0,
            light=10000.0,
        )

        cycle = ensure_estimation_for_reading(reading, greenhouse=self.greenhouse)

        self.assertLessEqual(cycle.kf_R, 4.0)
        self.assertGreater(cycle.kf_K, 0.7)
        self.assertGreater(cycle.kf_x_posterior, 55.0)

    def test_ampc_uses_raw_sensor_when_kalman_posterior_diverges(self):
        base_ts = timezone.now() - timedelta(minutes=20)
        raw_values = [58.0, 59.0, 60.0, 59.0]
        posterior_values = [40.0, 41.0, 40.5, 40.0]
        for index, (raw, posterior) in enumerate(zip(raw_values, posterior_values)):
            EstimationCycle.objects.create(
                sample_ts=base_ts + timedelta(minutes=index * 5),
                cycle_index=index,
                greenhouse=self.greenhouse,
                slice_type='online',
                source_type='live',
                validation_status='valid',
                preprocess_status=EstimationCycle.PreprocessStatus.VALID,
                cycle_status=EstimationCycle.CycleStatus.OK,
                adaptive_status=EstimationCycle.AdaptiveStatus.R_UPDATED,
                raw_soil_moisture=raw,
                raw_temperature=28.0,
                raw_humidity=70.0,
                raw_light=10000.0,
                raw_drip=0.0,
                raw_mist=0.0,
                raw_fan=0.0,
                arx_predicted=40.0,
                kf_x_prior=40.0,
                kf_P_prior=1.0,
                kf_innovation=raw - 40.0,
                kf_R=25.0,
                kf_K=0.02,
                kf_x_posterior=posterior,
                kf_P_posterior=0.5,
                ingest_dedupe_key=f'bad-kf-history-{index}',
            )

        audit = run_auto_recommendation(
            create_command_if_auto=False,
            user=self.user,
            greenhouse_id=self.greenhouse.id,
        )

        self.assertEqual(audit.safety_status, 'safe')
        self.assertTrue(audit.state_snapshot['used_raw_fallback'])
        self.assertEqual(audit.state_snapshot['control_soil_moisture'], raw_values[-1])
        self.assertGreater(min(audit.predicted_soil_moisture[:3]), 50.0)

    def test_pipeline_cycles_is_not_a_runtime_table(self):
        from django.db import connection

        self.assertNotIn('pipeline_cycles', connection.introspection.table_names())
