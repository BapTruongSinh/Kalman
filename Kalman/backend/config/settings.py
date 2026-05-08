"""
Cấu hình Django cho backend Adaptive Kalman pipeline.

Cách dùng
---------
- Copy ``.env.example`` thành ``.env`` rồi điền ``DJANGO_SECRET_KEY`` và các biến DB_*.
- **Local / demo v1**: ``DJANGO_ENV=development`` (mặc định) - bật DEBUG,
  CORS thoáng hơn; dashboard API mặc định **AllowAny** nếu không đặt
  ``DASHBOARD_REQUIRE_AUTH``.
- **Production / public v2**: ``DJANGO_ENV=production`` - bắt buộc có
  ``DJANGO_SECRET_KEY``; các API đọc cho dashboard mặc định **IsAuthenticated**
  trừ khi chủ động đặt ``DASHBOARD_REQUIRE_AUTH=false``.

Kiểm tra::

    python manage.py check
    python manage.py check --deploy   # dùng với DJANGO_ENV=production + secret thật
"""

import os
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def _split_csv_or_whitespace(value: str) -> list[str]:
    """Tách danh sách env bằng dấu phẩy hoặc khoảng trắng để tương thích ngược."""
    return [p.strip() for p in re.split(r"[\s,]+", value.strip()) if p.strip()]

# --- Đường dẫn ---
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent.parent

# Load .env nếu có, thường dùng khi chạy development.
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# --- Môi trường ---
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"

# --- Bảo mật: SECRET_KEY & DEBUG ---
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

# HTTPS / cookie cho production, có thể chỉnh khi chạy sau reverse proxy.
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
        # Định dạng: "HTTP_X_FORWARDED_PROTO,https"
        parts = [p.strip() for p in _proxy.split(",", 1)]
        if len(parts) == 2:
            SECURE_PROXY_SSL_HEADER = (parts[0], parts[1])

    _csrf_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
    if _csrf_origins:
        CSRF_TRUSTED_ORIGINS = _split_csv_or_whitespace(_csrf_origins)

# --- Ứng dụng ---
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

# --- Middleware: bảo mật, CORS, session, CSRF, auth, X-Frame ---
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
# Mặc định chỉ bắt auth cho dashboard GET API khi ở production.
_dash_auth_raw = os.environ.get("DASHBOARD_REQUIRE_AUTH")
if _dash_auth_raw is None:
    _REQUIRE_AUTH = IS_PRODUCTION
else:
    _REQUIRE_AUTH = _dash_auth_raw.strip().lower() in ("1", "true", "yes")

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
    CORS_ALLOWED_ORIGINS = _split_csv_or_whitespace(_cors_origins)
else:
    CORS_ALLOW_ALL_ORIGINS = DEBUG

# --- Session: cần cho SessionAuthentication / admin / login dashboard sau này ---
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

# --- Prediction artifact ---
# Runtime live/online ingestion uses the pre-built ARX artifact from the sibling
# ARX research folder. The path can be overridden for deployment, but is never
# supplied by an API request.
ARX_MODEL_PATH = os.environ.get(
    "ARX_MODEL_PATH",
    str(REPO_ROOT / "ARX" / "arx_model.json"),
)
