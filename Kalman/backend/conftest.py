"""
Root pytest configuration for the Kalman backend.

Sets ``DJANGO_SETTINGS_MODULE`` before Django is loaded, so that any test
module that imports Django models (e.g. ``estimation.run_config.service``)
finds the settings already configured.

pytest-django is used for database access in ``TestCase``-based tests.
Pure-Python tests (estimation.kalman, estimation.prediction,
estimation.ingestion) continue to work without database setup.
"""

import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Predictable defaults for the suite: a local .env with DJANGO_ENV=production
# would otherwise default DASHBOARD_REQUIRE_AUTH on and break unauthenticated
# APIClient tests. Explicit exports in the shell still win (setdefault).
os.environ.setdefault("DJANGO_ENV", "development")
os.environ.setdefault("DASHBOARD_REQUIRE_AUTH", "false")

django.setup()
