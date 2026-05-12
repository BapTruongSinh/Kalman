from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from api.models import (
    AMPCRecommendation,
    Alert,
    AMPCSchedulerState,
    ControlState,
    Device,
    DeviceCommand,
    DeviceState,
    EstimationCycle,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
    SensorData,
)
from api.ampc import run_auto_recommendation
from api.ampc_scheduler import get_scheduler_state, run_due_once
from api.et0 import ET0Failure, ET0Reading
from api.estimation import ensure_estimation_for_reading, latest_estimation
from api.services import ingest_sensor_payload


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

    def test_legacy_dashboard_sensor_device_alert_endpoints_are_owner_scoped(self):
        now = timezone.now()
        owner_controller = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner ESP32',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            status=Device.DeviceStatus.ONLINE,
            last_seen_at=now,
        )
        other_controller = Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other ESP32',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            status=Device.DeviceStatus.ONLINE,
            last_seen_at=now,
        )
        owner_fan = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner Fan',
            code='fan-shared',
            device_type=Device.DeviceType.FAN,
        )
        other_fan = Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other Fan',
            code='fan-shared',
            device_type=Device.DeviceType.FAN,
        )
        owner_reading = SensorData.objects.create(
            greenhouse=self.greenhouse,
            recorded_at=now,
            soil_moisture=61.0,
            temperature=28.0,
            humidity=70.0,
            light=100.0,
        )
        SensorData.objects.create(
            greenhouse=self.other_greenhouse,
            recorded_at=now + timedelta(minutes=1),
            soil_moisture=12.0,
            temperature=40.0,
            humidity=20.0,
            light=999.0,
        )
        owner_alert = Alert.objects.create(level=Alert.Level.WARNING, title='Owner', message='owner', device=owner_fan)
        other_alert = Alert.objects.create(level=Alert.Level.ERROR, title='Other', message='other', device=other_fan)

        response = self.client.get('/api/dashboard/overview/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['latest']['id'], owner_reading.id)
        self.assertEqual(payload['device_count'], 1)
        self.assertEqual([row['id'] for row in payload['recent_alerts']], [owner_alert.id])

        response = self.client.get('/api/sensor-readings/latest/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], owner_reading.id)

        response = self.client.get('/api/sensor-readings/history/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['items']], [owner_reading.id])

        response = self.client.get('/api/sensor-readings/chart/?metric=soil_moisture&hours=24')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([point['value'] for point in response.json()['points']], [61.0])

        response = self.client.get('/api/devices/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['id'] for row in response.json()}, {owner_controller.id, owner_fan.id})
        self.assertNotIn(other_controller.id, {row['id'] for row in response.json()})

        response = self.client.get('/api/alerts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()], [owner_alert.id])

        response = self.client.post(f'/api/alerts/{other_alert.id}/mark_read/', {}, format='json')
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/api/alerts/mark_all_read/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated'], 1)
        other_alert.refresh_from_db()
        self.assertFalse(other_alert.is_read)

    def test_device_control_endpoints_are_owner_scoped(self):
        owner_pump = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner Pump',
            code='pump-shared',
            device_type=Device.DeviceType.PUMP,
        )
        other_pump = Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other Pump',
            code='pump-shared',
            device_type=Device.DeviceType.PUMP,
        )

        response = self.client.post(f'/api/devices/{other_pump.id}/toggle/', {}, format='json')
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            f'/api/devices/{other_pump.id}/command/',
            {'command': 'set_power', 'value': 'on'},
            format='json',
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(f'/api/devices/{owner_pump.id}/toggle/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceCommand.objects.get().device_id, owner_pump.id)

    def test_ingest_pending_and_ack_commands_are_scoped_by_controller_token(self):
        owner_controller = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner ESP32',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            api_token='owner-controller-token',
        )
        other_controller = Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other ESP32',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            api_token='other-controller-token',
        )
        owner_pump = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner Pump',
            code='pump-1',
            device_type=Device.DeviceType.PUMP,
        )
        other_pump = Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other Pump',
            code='pump-1',
            device_type=Device.DeviceType.PUMP,
        )
        owner_cmd = DeviceCommand.objects.create(device=owner_pump, command='set_power', value='on')
        other_cmd = DeviceCommand.objects.create(device=other_pump, command='set_power', value='on')
        esp_client = APIClient(HTTP_HOST='127.0.0.1')

        response = esp_client.get(
            '/api/ingest/commands/pending/',
            HTTP_X_DEVICE_TOKEN=owner_controller.api_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()], [owner_cmd.id])

        response = esp_client.get(
            '/api/ingest/commands/pending/',
            HTTP_X_DEVICE_TOKEN=other_controller.api_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()], [other_cmd.id])

        response = esp_client.post(
            f'/api/ingest/commands/{other_cmd.id}/ack/',
            {'status': DeviceCommand.CommandStatus.ACK},
            format='json',
            HTTP_X_DEVICE_TOKEN=owner_controller.api_token,
        )
        self.assertEqual(response.status_code, 404)

        response = esp_client.post(
            f'/api/ingest/commands/{owner_cmd.id}/ack/',
            {'status': DeviceCommand.CommandStatus.ACK},
            format='json',
            HTTP_X_DEVICE_TOKEN=owner_controller.api_token,
        )
        self.assertEqual(response.status_code, 200)
        owner_cmd.refresh_from_db()
        self.assertEqual(owner_cmd.status, DeviceCommand.CommandStatus.ACK)

        response = esp_client.get('/api/ingest/commands/pending/')
        self.assertEqual(response.status_code, 403)

    def test_websocket_auth_helpers_require_valid_tokens(self):
        from api.consumer import auth_device_sync, auth_frontend_token_sync

        controller = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner ESP32',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            api_token='owner-ws-token',
        )

        self.assertIsNone(auth_device_sync('esp32-main', None))
        self.assertIsNone(auth_device_sync('esp32-main', settings.INGEST_DEVICE_TOKEN))
        self.assertIsNone(auth_device_sync('esp32-main', 'bad-token'))
        self.assertEqual(
            auth_device_sync('esp32-main', controller.api_token),
            {'id': controller.id, 'code': controller.code, 'greenhouse_id': self.greenhouse.id},
        )

        self.assertIsNone(auth_frontend_token_sync(None))
        self.assertIsNone(auth_frontend_token_sync('bad-jwt'))
        access = str(AccessToken.for_user(self.user))
        self.assertEqual(auth_frontend_token_sync(access)['greenhouse_id'], self.greenhouse.id)

    def test_device_code_can_repeat_across_greenhouses(self):
        Device.objects.create(
            greenhouse=self.greenhouse,
            name='Owner Pump',
            code='shared-device-code',
            device_type=Device.DeviceType.PUMP,
        )
        Device.objects.create(
            greenhouse=self.other_greenhouse,
            name='Other Pump',
            code='shared-device-code',
            device_type=Device.DeviceType.PUMP,
        )

        self.assertEqual(Device.objects.filter(code='shared-device-code').count(), 2)

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
            singleton_key=ControlState.singleton_key_for_greenhouse(self.greenhouse.id),
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
            singleton_key=ControlState.singleton_key_for_greenhouse(self.greenhouse.id),
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

    def test_fao_ampc_long_model_error_persists_fail_closed_audit(self):
        self._seed_estimation_history(0.0)
        reason_max_length = AMPCRecommendation._meta.get_field('reason').max_length
        status_max_length = AMPCRecommendation._meta.get_field('safety_status').max_length

        with (
            patch('api.ampc.get_hourly_et0', return_value=self._et0_reading()),
            patch('api.ampc.ARXPlantModel.load_artifact', side_effect=RuntimeError('x' * 300)),
        ):
            audit = run_auto_recommendation(
                create_command_if_auto=False,
                user=self.user,
                greenhouse_id=self.greenhouse.id,
            )

        self.assertEqual(audit.safety_status, 'model_error')
        self.assertLessEqual(len(audit.safety_status), status_max_length)
        self.assertEqual(audit.pump_seconds, 0.0)
        self.assertFalse(audit.command_created)
        self.assertEqual(audit.actuator_status, AMPCRecommendation.ActuatorStatus.DISABLED)
        self.assertEqual(len(audit.reason), reason_max_length)
        self.assertEqual(audit.reason, 'x' * reason_max_length)
        self.assertEqual(DeviceCommand.objects.count(), 0)

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

    def test_reading_ingest_rejects_malformed_numeric_payload(self):
        cases = ['abc', 'Infinity']

        for value in cases:
            with self.subTest(value=value):
                response = self.client.post(
                    '/api/ingest/readings/',
                    {
                        'recorded_at': timezone.now().isoformat(),
                        'soil_moisture': value,
                        'temperature': 28.0,
                        'humidity': 70.0,
                        'light': 10000.0,
                    },
                    format='json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn('soil_moisture', response.json())
        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)

    def test_reading_ingest_rejects_out_of_range_sensor_payload(self):
        cases = [
            ({'soil_moisture': 100000.0}, 'soil_moisture'),
            ({'soil_moisture': -0.01}, 'soil_moisture'),
            ({'humidity': 100.01}, 'humidity'),
            ({'temperature': 100.0}, 'temperature'),
            ({'light': 100000000.0}, 'light'),
        ]

        for override, field in cases:
            with self.subTest(field=field, override=override):
                payload = {
                    'recorded_at': timezone.now().isoformat(),
                    'soil_moisture': 60.0,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    **override,
                }
                response = self.client.post(
                    '/api/ingest/readings/',
                    payload,
                    format='json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)

    def test_ingest_samples_rejects_out_of_range_sensor_payload(self):
        cases = [
            ({'soil_moisture': 100000.0}, 'soil_moisture'),
            ({'soil_moisture': -0.01}, 'soil_moisture'),
            ({'humidity': 100.01}, 'humidity'),
            ({'temperature': 100.0}, 'temperature'),
            ({'light': 100000000.0}, 'light'),
        ]

        for override, field in cases:
            with self.subTest(field=field, override=override):
                payload = {
                    'run_id': self.run.id,
                    'timestamp': timezone.now().isoformat(),
                    'soil_moisture': 60.0,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    'drip': 0.0,
                    'mist': 0.0,
                    'fan': 0.0,
                    **override,
                }
                response = self.client.post(
                    '/api/ingest/samples/',
                    payload,
                    format='json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)

    def test_ingest_samples_rejects_non_finite_actuator_payload(self):
        response = self.client.post(
            '/api/ingest/samples/',
            data=(
                f'{{"run_id": {self.run.id},'
                f'"timestamp": "{timezone.now().isoformat()}",'
                '"soil_moisture": 60.0,'
                '"temperature": 28.0,'
                '"humidity": 70.0,'
                '"light": 10000.0,'
                '"drip": 1e309,'
                '"mist": 0.0,'
                '"fan": 0.0}'
            ),
            content_type='application/json',
            HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('drip', response.json())
        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)

    def test_reading_ingest_rejects_non_finite_nested_json_payloads(self):
        cases = [
            ('"payload": {"drip": 1e309}', 'payload'),
            ('"metadata": {"bad": 1e309}', 'metadata'),
            ('"sensor_errors": {"dht": 1e309}', 'sensor_errors'),
        ]

        for override, field in cases:
            with self.subTest(field=field):
                response = self.client.post(
                    '/api/ingest/readings/',
                    data=(
                        '{"recorded_at": "' + timezone.now().isoformat() + '",'
                        '"soil_moisture": 60.0,'
                        '"temperature": 28.0,'
                        '"humidity": 70.0,'
                        '"light": 10000.0,'
                        f'{override}' +
                        '}'
                    ),
                    content_type='application/json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(Alert.objects.count(), 0)

    def test_ingest_heartbeat_rejects_oversized_text_payload(self):
        cases = [
            ({'firmware_version': 'v' * 51}, 'firmware_version'),
            ({'mode': 'MANUAL', 'manual_reason': 'r' * 256}, 'manual_reason'),
        ]

        for payload, field in cases:
            with self.subTest(field=field):
                response = self.client.post(
                    '/api/ingest/heartbeat/',
                    payload,
                    format='json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(ControlState.objects.count(), 0)

    def test_reading_ingest_rejects_oversized_text_and_unknown_sensor_errors(self):
        cases = [
            ({'firmware_version': 'v' * 51}, 'firmware_version'),
            ({'mode': 'MANUAL', 'manual_reason': 'r' * 256}, 'manual_reason'),
            ({'sensor_errors': {'sensor-name-that-is-not-allowed': True}}, 'sensor_errors'),
        ]

        for override, field in cases:
            with self.subTest(field=field):
                payload = {
                    'recorded_at': timezone.now().isoformat(),
                    'soil_moisture': 60.0,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    **override,
                }
                response = self.client.post(
                    '/api/ingest/readings/',
                    payload,
                    format='json',
                    HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)
        self.assertEqual(Alert.objects.count(), 0)
        self.assertEqual(ControlState.objects.count(), 0)

    def test_control_mode_rejects_oversized_reason(self):
        response = self.client.post(
            '/api/control/mode/',
            {'mode': 'MANUAL', 'reason': 'r' * 256},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('reason', response.json())
        self.assertEqual(ControlState.objects.count(), 0)

    def test_device_command_rejects_oversized_command_payload(self):
        pump = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Pump',
            code='pump-main',
            device_type=Device.DeviceType.PUMP,
        )
        cases = [
            ({'command': 'c' * 51, 'value': 'on'}, 'command'),
            ({'command': 'set_power', 'value': 'v' * 51}, 'value'),
        ]

        for payload, field in cases:
            with self.subTest(field=field):
                response = self.client.post(
                    f'/api/devices/{pump.id}/command/',
                    payload,
                    format='json',
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

        self.assertEqual(DeviceCommand.objects.count(), 0)
        self.assertEqual(DeviceState.objects.count(), 0)
        self.assertEqual(ControlState.objects.count(), 0)

    def test_device_command_rejects_non_finite_nested_payload(self):
        pump = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Pump',
            code='pump-main',
            device_type=Device.DeviceType.PUMP,
        )

        response = self.client.post(
            f'/api/devices/{pump.id}/command/',
            data='{"command": "set_power", "value": "on", "payload": {"bad": 1e309}}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('payload', response.json())
        self.assertEqual(DeviceCommand.objects.count(), 0)
        self.assertEqual(DeviceState.objects.count(), 0)
        self.assertEqual(ControlState.objects.count(), 0)

    def test_ingest_command_ack_rejects_invalid_status_payload(self):
        controller = Device.objects.create(
            greenhouse=self.greenhouse,
            name='ESP32 Main',
            code='esp32-main',
            device_type=Device.DeviceType.CONTROLLER,
            api_token='controller-token',
        )
        pump = Device.objects.create(
            greenhouse=self.greenhouse,
            name='Pump',
            code='pump-main',
            device_type=Device.DeviceType.PUMP,
        )
        cmd = DeviceCommand.objects.create(device=pump, command='set_power', value='on')
        cases = ['s' * 21, 'done']

        for status_value in cases:
            with self.subTest(status=status_value):
                response = self.client.post(
                    f'/api/ingest/commands/{cmd.id}/ack/',
                    {'status': status_value},
                    format='json',
                    HTTP_X_DEVICE_TOKEN=controller.api_token,
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn('status', response.json())

        cmd.refresh_from_db()
        self.assertEqual(cmd.status, DeviceCommand.CommandStatus.PENDING)
        self.assertIsNone(cmd.acked_at)

    def test_ingest_sensor_service_rejects_invalid_payload_before_db_write(self):
        with self.assertRaises(ValidationError):
            ingest_sensor_payload(
                {
                    'recorded_at': timezone.now(),
                    'soil_moisture': 100000.0,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    'payload': {'drip': 0.0},
                },
                greenhouse=self.greenhouse,
            )

        with self.assertRaises(ValidationError):
            ingest_sensor_payload(
                {
                    'recorded_at': timezone.now(),
                    'soil_moisture': 60.0,
                    'temperature': 28.0,
                    'humidity': 70.0,
                    'light': 10000.0,
                    'metadata': {'bad': float('inf')},
                },
                greenhouse=self.greenhouse,
            )

        self.assertEqual(SensorData.objects.count(), 0)
        self.assertEqual(Device.objects.count(), 0)
        self.assertEqual(EstimationCycle.objects.count(), 0)

    def test_reading_ingest_missing_soil_does_not_create_usable_kalman_state(self):
        response = self.client.post(
            '/api/ingest/readings/',
            {
                'recorded_at': timezone.now().isoformat(),
                'temperature': 28.0,
                'humidity': 70.0,
                'light': 10000.0,
            },
            format='json',
            HTTP_X_DEVICE_TOKEN=settings.INGEST_DEVICE_TOKEN,
        )

        self.assertEqual(response.status_code, 200)
        cycle = EstimationCycle.objects.get(id=response.json()['estimation_id'])
        self.assertIsNone(cycle.raw_soil_moisture)
        self.assertIsNone(cycle.kf_x_posterior)
        self.assertIsNone(latest_estimation(greenhouse=self.greenhouse))

    def test_ampc_error_does_not_queue_pump_command(self):
        profile = GreenhouseControlProfile.objects.get(greenhouse=self.greenhouse)
        profile.actuator_enabled = True
        profile.save(update_fields=['actuator_enabled', 'updated_at'])
        ControlState.objects.update_or_create(
            singleton_key=ControlState.singleton_key_for_greenhouse(self.greenhouse.id),
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
        state = get_scheduler_state(greenhouse=self.greenhouse)
        state.is_enabled = True
        state.next_run_at = timezone.now()
        state.save(update_fields=['is_enabled', 'next_run_at', 'updated_at'])

        response = self.client.post('/api/control/ampc-scheduler/stop/', {}, format='json')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['is_enabled'])
        self.assertIsNone(payload['next_run_at'])

    def test_ampc_scheduler_key_handles_large_greenhouse_ids(self):
        large_greenhouse = Greenhouse.objects.create(
            id=1_000_000_000,
            owner=self.user,
            name='GH-large-id',
        )

        state = get_scheduler_state(greenhouse=large_greenhouse)

        max_length = AMPCSchedulerState._meta.get_field('singleton_key').max_length
        self.assertLessEqual(len(state.singleton_key), max_length)
        self.assertEqual(state.singleton_key, 'gh:3b9aca00')
        self.assertEqual(state.greenhouse_id, large_greenhouse.id)

    def test_control_state_key_handles_large_greenhouse_ids_without_collision(self):
        first_greenhouse = Greenhouse.objects.create(
            id=1_000_000_000,
            owner=self.user,
            name='GH-control-large-a',
        )
        second_greenhouse = Greenhouse.objects.create(
            id=1_000_000_001,
            owner=self.user,
            name='GH-control-large-b',
        )

        first_key = ControlState.singleton_key_for_greenhouse(first_greenhouse.id)
        second_key = ControlState.singleton_key_for_greenhouse(second_greenhouse.id)
        first_state, _ = ControlState.objects.get_or_create(
            greenhouse=first_greenhouse,
            defaults={'singleton_key': first_key},
        )
        second_state, _ = ControlState.objects.get_or_create(
            greenhouse=second_greenhouse,
            defaults={'singleton_key': second_key},
        )

        max_length = ControlState._meta.get_field('singleton_key').max_length
        self.assertLessEqual(len(first_key), max_length)
        self.assertLessEqual(len(second_key), max_length)
        self.assertNotEqual(first_key, second_key)
        self.assertEqual(first_state.singleton_key, 'gh:3b9aca00')
        self.assertEqual(second_state.singleton_key, 'gh:3b9aca01')

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

    def test_forecast_uses_newer_estimation_cycles_for_latest_and_history(self):
        sensor_ts = timezone.now() - timedelta(days=1)
        SensorData.objects.create(
            greenhouse=self.greenhouse,
            recorded_at=sensor_ts,
            soil_moisture=40.0,
            temperature=24.0,
            humidity=60.0,
            light=1000.0,
        )
        base_ts = timezone.now().replace(second=0, microsecond=0)
        latest_cycle = None
        for index, soil in enumerate([58.0, 59.0, 60.0, 61.0, 62.0, 63.0]):
            latest_cycle = EstimationCycle.objects.create(
                sample_ts=base_ts + timedelta(minutes=index * 5),
                cycle_index=index,
                greenhouse=self.greenhouse,
                slice_type='online',
                source_type='live',
                validation_status='valid',
                preprocess_status=EstimationCycle.PreprocessStatus.VALID,
                cycle_status=EstimationCycle.CycleStatus.OK,
                adaptive_status=EstimationCycle.AdaptiveStatus.R_SKIPPED,
                raw_soil_moisture=soil,
                raw_temperature=28.0 + index,
                raw_humidity=70.0 + index,
                raw_light=10000.0 + index,
                raw_drip=0.0,
                raw_mist=0.0,
                raw_fan=0.0,
                arx_predicted=soil,
                kf_x_prior=soil,
                kf_P_prior=1.0,
                kf_innovation=0.0,
                kf_R=1.0,
                kf_K=0.8,
                kf_x_posterior=soil + 0.5,
                kf_P_posterior=0.5,
                ingest_dedupe_key=f'forecast-estimation-history-{index}',
            )

        response = self.client.get('/api/forecast/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['latest']['id'], latest_cycle.id)
        self.assertEqual(payload['latest']['recorded_at'], latest_cycle.sample_ts.isoformat().replace('+00:00', 'Z'))
        self.assertEqual(payload['latest']['soil_moisture'], latest_cycle.raw_soil_moisture)
        self.assertEqual(payload['latest']['payload']['source'], 'estimation_cycle')
        self.assertEqual([row['soil_moisture'] for row in payload['history']], [58.0, 59.0, 60.0, 61.0, 62.0, 63.0])

    def test_malformed_query_params_return_400(self):
        cases = [
            '/api/sensor-readings/chart/?metric=soil_moisture&hours=bad',
            '/api/sensor-readings/history/?page=bad',
            '/api/sensor-readings/history/?hours=bad',
            f'/api/runs/{self.run.id}/series/?limit=bad',
        ]

        for url in cases:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 400)

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

    def test_live_kalman_dedupe_is_scoped_by_greenhouse_without_run(self):
        sample_ts = timezone.now()
        first_reading = SensorData.objects.create(
            greenhouse=self.greenhouse,
            recorded_at=sample_ts,
            soil_moisture=60.0,
            temperature=28.0,
            humidity=70.0,
            light=10000.0,
        )
        second_reading = SensorData.objects.create(
            greenhouse=self.other_greenhouse,
            recorded_at=sample_ts,
            soil_moisture=42.0,
            temperature=27.0,
            humidity=71.0,
            light=9000.0,
        )

        first_cycle = ensure_estimation_for_reading(first_reading, greenhouse=self.greenhouse)
        second_cycle = ensure_estimation_for_reading(second_reading, greenhouse=self.other_greenhouse)
        repeated_second = ensure_estimation_for_reading(second_reading, greenhouse=self.other_greenhouse)

        self.assertNotEqual(first_cycle.id, second_cycle.id)
        self.assertEqual(first_cycle.greenhouse_id, self.greenhouse.id)
        self.assertEqual(second_cycle.greenhouse_id, self.other_greenhouse.id)
        self.assertEqual(repeated_second.id, second_cycle.id)
        self.assertEqual(EstimationCycle.objects.filter(ingest_dedupe_key=first_cycle.ingest_dedupe_key).count(), 2)

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
