from __future__ import annotations

from datetime import datetime, timedelta, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from api.et0 import ET0Failure, ET0Reading, OpenMeteoError, get_hourly_et0
from api.models import Greenhouse, GreenhouseControlProfile


class FakeOpenMeteoClient:
    def __init__(self, payload=None, exc: Exception | None = None):
        self.payload = payload
        self.exc = exc
        self.calls = []

    def fetch_hourly_et0(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.payload


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'open-meteo-et0-tests',
        }
    },
    OPEN_METEO_ET0_RECENT_CACHE_SECONDS=6 * 60 * 60,
)
class OpenMeteoET0ServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(username='et0-owner', password='pass')
        self.greenhouse = Greenhouse.objects.create(owner=self.user, name='ET0 GH')
        GreenhouseControlProfile.objects.create(
            greenhouse=self.greenhouse,
            latitude=16.0471,
            longitude=108.2068,
        )
        self.when = datetime(2026, 5, 12, 9, 23, tzinfo=datetime_timezone.utc)
        self.now = datetime(2026, 5, 12, 9, 30, tzinfo=datetime_timezone.utc)

    def tearDown(self):
        cache.clear()

    def test_successful_api_response_returns_hourly_and_step_et0(self):
        client = FakeOpenMeteoClient(
            payload={
                'hourly': {
                    'time': ['2026-05-12T09:00'],
                    'et0_fao_evapotranspiration': [0.72],
                }
            }
        )

        result = get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=900,
            client=client,
            now=self.now,
        )

        self.assertIsInstance(result, ET0Reading)
        self.assertEqual(result.source, 'open_meteo')
        self.assertEqual(result.requested_hour, datetime(2026, 5, 12, 9, tzinfo=datetime_timezone.utc))
        self.assertAlmostEqual(result.et0_hour_mm, 0.72)
        self.assertAlmostEqual(result.et0_step_mm, 0.18)
        self.assertEqual(client.calls[0]['target_hour'], result.requested_hour)

    def test_exact_hour_cache_hit_skips_external_api(self):
        success_client = FakeOpenMeteoClient(
            payload={
                'hourly': {
                    'time': ['2026-05-12T09:00'],
                    'et0_fao_evapotranspiration': [0.48],
                }
            }
        )
        get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=300,
            client=success_client,
            now=self.now,
        )
        failing_client = FakeOpenMeteoClient(exc=OpenMeteoError('network_down'))

        result = get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=300,
            client=failing_client,
            now=self.now + timedelta(minutes=5),
        )

        self.assertIsInstance(result, ET0Reading)
        self.assertEqual(result.source, 'cache')
        self.assertAlmostEqual(result.et0_step_mm, 0.04)
        self.assertEqual(failing_client.calls, [])

    def test_network_failure_uses_recent_valid_cache_when_fresh(self):
        success_client = FakeOpenMeteoClient(
            payload={
                'hourly': {
                    'time': ['2026-05-12T09:00'],
                    'et0_fao_evapotranspiration': [0.6],
                }
            }
        )
        get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=300,
            client=success_client,
            now=self.now,
        )
        failing_client = FakeOpenMeteoClient(exc=OpenMeteoError('timeout'))

        result = get_hourly_et0(
            self.greenhouse,
            self.when + timedelta(hours=1),
            step_seconds=600,
            client=failing_client,
            now=self.now + timedelta(minutes=30),
        )

        self.assertIsInstance(result, ET0Reading)
        self.assertEqual(result.source, 'recent_cache')
        self.assertEqual(len(failing_client.calls), 1)
        self.assertAlmostEqual(result.et0_hour_mm, 0.6)
        self.assertAlmostEqual(result.et0_step_mm, 0.1)

    def test_network_failure_without_cache_returns_fail_closed_result(self):
        client = FakeOpenMeteoClient(exc=OpenMeteoError('network_down'))

        result = get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=300,
            client=client,
            now=self.now,
        )

        self.assertIsInstance(result, ET0Failure)
        self.assertEqual(result.reason, 'open_meteo_et0_unavailable')
        self.assertTrue(result.fail_closed)
        self.assertEqual(result.pump_seconds, 0.0)

    def test_invalid_non_finite_et0_response_fails_closed(self):
        client = FakeOpenMeteoClient(
            payload={
                'hourly': {
                    'time': ['2026-05-12T09:00'],
                    'et0_fao_evapotranspiration': [float('inf')],
                }
            }
        )

        result = get_hourly_et0(
            self.greenhouse,
            self.when,
            step_seconds=300,
            client=client,
            now=self.now,
        )

        self.assertIsInstance(result, ET0Failure)
        self.assertEqual(result.reason, 'open_meteo_et0_unavailable')
        self.assertIn('et0_hour_mm_not_finite', result.detail)
        self.assertTrue(result.fail_closed)
