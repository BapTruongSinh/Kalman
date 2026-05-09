from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from pathlib import Path
from rest_framework.test import APIClient

from api.models import (
    AMPCRecommendation,
    EstimationCycle,
    ExperimentRun,
    Greenhouse,
    GreenhouseControlProfile,
)


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

    def test_pipeline_cycles_is_not_a_runtime_table(self):
        from django.db import connection

        self.assertNotIn('pipeline_cycles', connection.introspection.table_names())
