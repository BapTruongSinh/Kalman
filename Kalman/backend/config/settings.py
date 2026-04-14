"""
Django settings for the Adaptive Kalman pipeline backend.

Usage:
  - Copy .env.example to .env and fill in DJANGO_SECRET_KEY, DB_* variables.
  - Set DJANGO_ENV=production to disable DEBUG.
  - Run:  python manage.py migrate  to create all tables.
"""

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file when present (development). Does nothing in production if
# environment variables are already injected by the OS or container runtime.
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on OS environment variables

# --- Security ---
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.environ.get("DJANGO_ENV", "development") != "production"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1").split()

# --- Applications ---
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "estimation",
]

# --- Middleware ---
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# --- URL routing ---
ROOT_URLCONF = "config.urls"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

# --- CORS (allow all in dev; tighten in production via env) ---
_cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _cors_origins:
    CORS_ALLOWED_ORIGINS = _cors_origins.split()
else:
    CORS_ALLOW_ALL_ORIGINS = DEBUG

# --- Database (MySQL from XAMPP) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "kalman_greenhouse"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# --- Timezone ---
USE_TZ = True
TIME_ZONE = "Asia/Ho_Chi_Minh"
