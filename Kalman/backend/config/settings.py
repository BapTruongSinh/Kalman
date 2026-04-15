"""
Django settings for the Adaptive Kalman pipeline backend.

Usage
-----
- Copy ``.env.example`` to ``.env`` and set ``DJANGO_SECRET_KEY``, DB_* variables.
- **Local / v1 demo**: ``DJANGO_ENV=development`` (default) — DEBUG on, permissive CORS.
- **Production / v2 public**: ``DJANGO_ENV=production`` — ``DJANGO_SECRET_KEY`` is
  **mandatory** (no dev fallback); secure cookies / HSTS / SSL redirect follow env flags.

Verification::

    python manage.py check
    python manage.py check --deploy   # use with DJANGO_ENV=production + real secret
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env when present (development).
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# --- Environment ---
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"

# --- Security: SECRET_KEY & DEBUG ---
if IS_PRODUCTION:
    _secret = os.environ.get("DJANGO_SECRET_KEY", "").strip()
    if not _secret:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a non-empty value when DJANGO_ENV=production."
        )
    SECRET_KEY = _secret
    DEBUG = False
else:
    SECRET_KEY = os.environ.get(
        "DJANGO_SECRET_KEY",
        "dev-secret-key-change-in-production",
    )
    DEBUG = os.environ.get("DJANGO_DEBUG", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1").split()
    if h.strip()
]

# Production HTTPS / cookies (tunable for reverse-proxy setups)
if IS_PRODUCTION:
    _truthy = ("1", "true", "yes")

    SECURE_SSL_REDIRECT = (
        os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").strip().lower()
        in _truthy
    )
    SESSION_COOKIE_SECURE = (
        os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "true").strip().lower()
        in _truthy
    )
    CSRF_COOKIE_SECURE = (
        os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "true").strip().lower()
        in _truthy
    )
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = (
        os.environ.get("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "true").strip().lower()
        in _truthy
    )
    SECURE_HSTS_PRELOAD = (
        os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "false").strip().lower()
        in _truthy
    )
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

    _proxy = os.environ.get("DJANGO_SECURE_PROXY_SSL_HEADER", "").strip()
    if _proxy:
        # Format: "HTTP_X_FORWARDED_PROTO,https"
        parts = [p.strip() for p in _proxy.split(",", 1)]
        if len(parts) == 2:
            SECURE_PROXY_SSL_HEADER = (parts[0], parts[1])

    _csrf_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
    if _csrf_origins:
        CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]

# --- Applications ---
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "estimation",
]

# --- Middleware (SecurityMiddleware + CSRF + X-Frame + auth chain) ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# --- Django REST Framework ---
_REQUIRE_AUTH = (
    os.environ.get("DASHBOARD_REQUIRE_AUTH", "false").strip().lower()
    in ("1", "true", "yes")
)

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        (
            "rest_framework.permissions.IsAuthenticated"
            if _REQUIRE_AUTH
            else "rest_framework.permissions.AllowAny"
        ),
    ],
}

# --- CORS ---
_cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _cors_origins:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = DEBUG

# --- Sessions (required for SessionAuthentication / admin / future dashboard login) ---
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# --- Database ---
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

USE_TZ = True
TIME_ZONE = "Asia/Ho_Chi_Minh"
