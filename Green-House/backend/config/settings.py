from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'channels',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'smart_greenhouse'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': int(os.getenv('DB_PORT', '3306')),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'vi'
TIME_ZONE = os.getenv('DEFAULT_TIMEZONE', 'Asia/Ho_Chi_Minh')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'COERCE_DECIMAL_TO_STRING': False,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_LIFETIME_MINUTES', '1440'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://127.0.0.1:5173,http://localhost:5173',
    ).split(',')
    if origin.strip()
]

INGEST_DEVICE_TOKEN = os.getenv('INGEST_DEVICE_TOKEN', 'esp32-local-token')
APP_ZONE_ID = 1
ARX_MODEL_PATH = os.getenv(
    'ARX_MODEL_PATH',
    str(BASE_DIR.parent.parent / 'ARX' / 'arx_model.json'),
)
APP_ZONE_NAME = 'Nhà kính chính'

KALMAN_LIVE_Q = float(os.getenv('KALMAN_LIVE_Q', '12.0'))
KALMAN_LIVE_R0 = float(os.getenv('KALMAN_LIVE_R0', '1.0'))
KALMAN_LIVE_R_MIN = float(os.getenv('KALMAN_LIVE_R_MIN', '0.25'))
KALMAN_LIVE_R_MAX = float(os.getenv('KALMAN_LIVE_R_MAX', '4.0'))
KALMAN_LIVE_ALPHA = float(os.getenv('KALMAN_LIVE_ALPHA', '0.5'))
AMPC_RAW_FALLBACK_DELTA = float(os.getenv('AMPC_RAW_FALLBACK_DELTA', '8.0'))
KALMAN_TEST_DB_NAME = os.getenv('KALMAN_TEST_DB_NAME', 'kalman_greenhouse')

# Dev-friendly channel layer. Sau này scale nhiều process thì đổi sang Redis.
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}
