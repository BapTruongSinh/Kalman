from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import datetime, timedelta, timezone as datetime_timezone
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
from api.et0 import ET0Failure, ET0Reading
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

    def _et0_reading(self, et0_hour_mm=0.72):
        requested_hour = datetime(2026, 5, 12, 9, tzinfo=datetime_timezone.utc)
        return ET0Reading(
            greenhouse_id=self.greenhouse.id,
            requested_hour=requested_hour,
            et0_hour_mm=et0_hour_mm,
            et0_step_mm=et0_hour_mm * 300 / 3600,
            step_seconds=300,
            source='open_meteo',
            fetched_at=requested_hour,
        )

    def _et0_failure(self):
        return ET0Failure(
            greenhouse_id=self.greenhouse.id,
            requested_hour=datetime(2026, 5, 12, 9, tzinfo=datetime_timezone.utc),
            reason='open_meteo_et0_unavailable',
            detail='network_down',
        )

    def _seed_estimation_history(self, soil_moisture: float, count: int = 4) -> None:
        base_ts = timezone.now() - timedelta(minutes=(count - 1) * 5)
        for index in range(count):
            EstimationCycle.objects.create(
                sample_ts=base_ts + timedelta(minutes=index * 5),
                cycle_index=index,
                run=self.run,
                greenhouse=self.greenhouse,
                slice_type='online',
                source_type='live',
                validation_status='valid',
                preprocess_status=EstimationCycle.PreprocessStatus.VALID,
                cycle_status=EstimationCycle.CycleStatus.OK,
                adaptive_status=EstimationCycle.AdaptiveStatus.R_UPDATED,
                raw_soil_moisture=soil_moisture,
                raw_temperature=28.0,
                raw_humidity=70.0,
                raw_light=10000.0,
                raw_drip=0.0,
                raw_mist=0.0,
                raw_fan=0.0,
                arx_predicted=soil_moisture,
                kf_x_prior=soil_moisture,
                kf_P_prior=1.0,
                kf_innovation=0.0,
                kf_R=1.0,
                kf_K=0.8,
                kf_x_posterior=soil_moisture,
                kf_P_posterior=0.5,
                ingest_dedupe_key=f'fao-history-{soil_moisture}-{index}',
            )

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

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()):
            response = self.client.post(f'/api/greenhouses/{self.greenhouse.id}/ampc/recommendations/', {}, format='json')
        self.assertIn(response.status_code, {200, 202})
        self.assertIn('fao56', response.json()['state_snapshot'])

        audit = AMPCRecommendation.objects.get(id=response.json()['id'])
        self.assertEqual(audit.greenhouse_id, self.greenhouse.id)
        self.assertEqual(audit.run_id, self.run.id)
        self.assertNotEqual(audit.safety_status, 'model_error')
        self.assertNotIn('artifact not found', audit.reason.lower())
        self.assertGreater(len(audit.predicted_soil_moisture), 0)
        self.assertIn('fao56', audit.state_snapshot)
        self.assertIn('et0', audit.state_snapshot)
        self.assertIn('predicted_dr', audit.state_snapshot['fao56'])
        self.assertEqual(
            audit.state_snapshot['fao56']['predicted_soil_moisture'],
            audit.predicted_soil_moisture,
        )
        self.assertFalse(audit.command_created)

    def test_fao_ampc_wet_state_uses_dr_and_recommends_zero_pump(self):
        self._seed_estimation_history(100.0)

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()):
            audit = run_auto_recommendation(
                create_command_if_auto=False,
                user=self.user,
                greenhouse_id=self.greenhouse.id,
            )

        self.assertEqual(audit.safety_status, 'safe')
        self.assertEqual(audit.reason, 'field_capacity_or_wetter')
        self.assertEqual(audit.pump_seconds, 0.0)
        self.assertEqual(audit.state_snapshot['control_soil_moisture'], 100.0)
        self.assertEqual(audit.state_snapshot['fao56']['initial_dr'], 0.0)
        self.assertEqual(audit.state_snapshot['et0']['source'], 'open_meteo')

    def test_fao_ampc_dry_stressed_state_recommends_nonzero_pump(self):
        self._seed_estimation_history(0.0)

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()):
            audit = run_auto_recommendation(
                create_command_if_auto=False,
                user=self.user,
                greenhouse_id=self.greenhouse.id,
            )

        self.assertEqual(audit.safety_status, 'safe')
        self.assertEqual(audit.reason, 'above_raw_stress')
        self.assertGreater(audit.pump_seconds, 0.0)
        self.assertGreater(
            audit.state_snapshot['fao56']['initial_dr'],
            audit.state_snapshot['fao56']['raw'],
        )
        self.assertGreater(len(audit.predicted_soil_moisture), 0)

    def test_fao_ampc_et0_unavailable_fails_closed_and_queues_no_command(self):
        self._seed_estimation_history(0.0)
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
            code='pump-et0-fail',
            device_type=Device.DeviceType.PUMP,
            status=Device.DeviceStatus.ONLINE,
        )

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_failure()):
            audit = run_auto_recommendation(
                create_command_if_auto=True,
                user=self.user,
                greenhouse_id=self.greenhouse.id,
            )

        self.assertEqual(audit.safety_status, 'pump_off_failsafe')
        self.assertEqual(audit.reason, 'open_meteo_et0_unavailable')
        self.assertEqual(audit.pump_seconds, 0.0)
        self.assertFalse(audit.command_created)
        self.assertEqual(audit.actuator_status, AMPCRecommendation.ActuatorStatus.UNSAFE_SKIPPED)
        self.assertEqual(DeviceCommand.objects.count(), 0)
        self.assertEqual(audit.state_snapshot['et0']['fail_closed'], True)

    def test_fao_ampc_invalid_db_profile_fails_closed_and_queues_no_command(self):
        self._seed_estimation_history(0.0)
        profile = GreenhouseControlProfile.objects.get(greenhouse=self.greenhouse)
        profile.actuator_enabled = True
        profile.save(update_fields=['actuator_enabled', 'updated_at'])
        GreenhouseControlProfile.objects.filter(pk=profile.pk).update(root_depth_m=0.0)
        ControlState.objects.update_or_create(
            singleton_key=f'greenhouse:{self.greenhouse.id}'[:20],
            defaults={'greenhouse': self.greenhouse, 'mode': ControlState.Mode.AUTO},
        )
        Device.objects.create(
            greenhouse=self.greenhouse,
            name='Pump',
            code='pump-invalid-profile',
            device_type=Device.DeviceType.PUMP,
            status=Device.DeviceStatus.ONLINE,
        )

        with patch('api.ampc.get_hourly_et0') as et0_service:
            audit = run_auto_recommendation(
                create_command_if_auto=True,
                user=self.user,
                greenhouse_id=self.greenhouse.id,
            )

        et0_service.assert_not_called()
        self.assertEqual(audit.safety_status, 'config_error')
        self.assertTrue(audit.reason.startswith('invalid_fao_config:'))
        self.assertEqual(audit.pump_seconds, 0.0)
        self.assertFalse(audit.command_created)
        self.assertEqual(audit.actuator_status, AMPCRecommendation.ActuatorStatus.UNSAFE_SKIPPED)
        self.assertEqual(DeviceCommand.objects.count(), 0)
        self.assertEqual(audit.state_snapshot['fail_closed'], True)
        self.assertIn('root_depth_m must be > 0', audit.state_snapshot['config_error'])

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

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()):
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

    def test_auto_settings_saves_and_loads_fao56_physical_fields(self):
        response = self.client.patch(
            '/api/auto-settings/',
            {
                'latitude': 16.05,
                'longitude': 108.21,
                'soil_type': 'light_loam',
                'root_depth_m': 0.35,
                'depletion_fraction_p': 0.45,
                'pump_efficiency': 0.75,
                'pump_flow_lps': 0.03,
                'irrigation_area_m2': 0.5,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['soil_type'], 'light_loam')
        self.assertEqual(payload['theta_fc'], 0.15)
        self.assertEqual(payload['theta_wp'], 0.06)
        self.assertEqual(payload['theta_sat'], 0.45)
        self.assertEqual(payload['root_depth_m'], 0.35)

        response = self.client.get('/api/auto-settings/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['latitude'], 16.05)
        self.assertEqual(payload['longitude'], 108.21)
        self.assertEqual(payload['pump_efficiency'], 0.75)
        self.assertEqual(payload['irrigation_area_m2'], 0.5)

    def test_greenhouse_control_profile_saves_and_loads_fao56_physical_fields(self):
        response = self.client.patch(
            f'/api/greenhouses/{self.greenhouse.id}/control-profile/',
            {
                'soil_type': 'clay_loam',
                'theta_fc': 0.36,
                'theta_wp': 0.24,
                'theta_sat': 0.46,
                'root_depth_m': 0.4,
                'depletion_fraction_p': 0.55,
                'pump_efficiency': 0.9,
                'pump_flow_lps': 0.04,
                'irrigation_area_m2': 0.75,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['soil_type'], 'clay_loam')
        self.assertEqual(payload['theta_fc'], 0.36)
        self.assertEqual(payload['theta_wp'], 0.24)
        self.assertEqual(payload['theta_sat'], 0.46)

        response = self.client.get(f'/api/greenhouses/{self.greenhouse.id}/control-profile/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['root_depth_m'], 0.4)
        self.assertEqual(payload['depletion_fraction_p'], 0.55)
        self.assertEqual(payload['pump_flow_lps'], 0.04)

    def test_fao56_invalid_physical_ordering_is_rejected(self):
        response = self.client.patch(
            f'/api/greenhouses/{self.greenhouse.id}/control-profile/',
            {
                'theta_wp': 0.36,
                'theta_fc': 0.32,
                'theta_sat': 0.45,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        profile = GreenhouseControlProfile.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(profile.theta_wp, 0.15)
        self.assertEqual(profile.theta_fc, 0.32)

    def test_fao56_non_finite_and_out_of_range_values_are_rejected(self):
        endpoint = f'/api/greenhouses/{self.greenhouse.id}/control-profile/'
        cases = [
            ({'root_depth_m': 'Infinity'}, 'root_depth_m'),
            ({'pump_flow_lps': 'Infinity'}, 'pump_flow_lps'),
            ({'irrigation_area_m2': 'NaN'}, 'irrigation_area_m2'),
            ({'latitude': 'Infinity'}, 'latitude'),
            ({'latitude': 91.0}, 'latitude'),
            ({'longitude': -181.0}, 'longitude'),
        ]

        for payload, field in cases:
            with self.subTest(field=field, payload=payload):
                response = self.client.patch(endpoint, payload, format='json')

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_auto_settings_rejects_non_finite_fao56_values(self):
        response = self.client.patch(
            '/api/auto-settings/',
            {'pump_efficiency': 'NaN'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pump_efficiency', response.json())

    def test_auto_settings_rejects_invalid_runtime_config_values(self):
        cases = [
            ({'crop_kc': -0.1}, 'crop_kc'),
            ({'weight_band': -1.0}, 'cost_band_violation'),
            ({'weight_water': -1.0}, 'cost_water_use'),
            ({'weight_switch': -1.0}, 'cost_switching'),
            ({'weight_daily': -1.0}, 'cost_daily_cap_excess'),
            ({'weight_terminal': -1.0}, 'cost_terminal_band_violation'),
            ({'soft_daily_pump_cap_seconds': 0.0}, 'soft_daily_pump_cap_seconds'),
        ]

        for payload, field in cases:
            with self.subTest(field=field, payload=payload):
                response = self.client.patch('/api/auto-settings/', payload, format='json')

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_other_users_greenhouse_control_profile_cannot_be_updated(self):
        response = self.client.patch(
            f'/api/greenhouses/{self.other_greenhouse.id}/control-profile/',
            {'root_depth_m': 0.6},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            GreenhouseControlProfile.objects.filter(
                greenhouse=self.other_greenhouse,
                root_depth_m=0.6,
            ).exists()
        )

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

    def test_mpc_test_series_filters_seed_tag_before_limit(self):
        tagged = AMPCRecommendation.objects.create(
            greenhouse=self.greenhouse,
            pump_seconds=12.0,
            step_seconds=300,
            safety_status='safe',
            reason='manual_seed',
            predicted_soil_moisture=[61.0],
            target_band={'low': 55.0, 'high': 65.0},
            config_snapshot={'mpc_test_source': 'manual_mpc_test_seed'},
            state_snapshot={
                'sample_ts': timezone.now().isoformat(),
                'actual_soil_moisture': 60.0,
                'mpc_soil_moisture': 61.0,
            },
        )
        for index in range(501):
            AMPCRecommendation.objects.create(
                greenhouse=self.greenhouse,
                pump_seconds=0.0,
                step_seconds=300,
                safety_status='safe',
                reason=f'live_{index}',
                predicted_soil_moisture=[60.0],
                target_band={'low': 55.0, 'high': 65.0},
                config_snapshot={'source': 'live'},
            )

        response = self.client.get('/api/mpc-test/series/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total_selected'], 1)
        self.assertEqual(payload['points'][0]['reason'], tagged.reason)

    @override_settings(DEBUG=False)
    def test_kalman_test_series_requires_staff_outside_debug(self):
        response = self.client.get('/api/kalman-test/series/')

        self.assertEqual(response.status_code, 403)

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

        with patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()):
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
