from pathlib import Path
import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY","dev-only")
DEBUG = True
APPEND_SLASH = True

ALLOWED_HOSTS = ["*", "localhost", "127.0.0.1"]

TENANT_PROVISIONING_TOKEN = os.getenv("TENANT_PROVISIONING_TOKEN", "")
ADMIN_PROVISIONING_TOKEN  = os.getenv("ADMIN_PROVISIONING_TOKEN", "")


INSTALLED_APPS = []  # será montado a partir de SHARED_APPS + TENANT_APPS

# apps que moram no PUBLIC schema (mínimo)
SHARED_APPS = (
    "django_tenants",
    "django.contrib.contenttypes",
    # nada de auth/admin/sessions aqui
    "tenants",   # gerenciamento de tenants/domínios via API
    "commons",   # health/time endpoints
)

# apps que moram nos schemas de cada tenant
TENANT_APPS = (
    "django.contrib.contenttypes",        # precisa repetir
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",

    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",

    "usuario",   # AUTH_USER_MODEL
    "filial",
    "terminal",
    "fiscal",
    "enderecos",
    "produtos",
    "metodoPagamento",
    "tef",
    "vendas",
    "promocoes",
    # (demais apps nas próximas sprints: produto, codigobarras, caixa, pdv, pagamentos, sync, etc.)
)

INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "commons.middleware.RequestLogMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"              # urls para tenants
PUBLIC_SCHEMA_URLCONF = "config.urls_public"  # urls do schema público

CORS_ALLOW_ALL_ORIGINS = True

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.getenv("PGDATABASE","pdvdados"),
        "USER": os.getenv("PGUSER","postgres"),
        "PASSWORD": os.getenv("PGPASSWORD","29032013"),
        "HOST": os.getenv("PGHOST","127.0.0.1"),
        "PORT": os.getenv("PGPORT","5432"),
        "TEST": {
            # importante: fixar o nome do banco de testes
            "NAME": "test_pdvdados",
            # opcional: usar transações em schema tests
            "MIRROR": None,
        },
    }
}

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

AUTH_USER_MODEL = "usuario.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/hour",
        "login": "10/minute",
        "pin": "10/minute",
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

SPECTACULAR_SETTINGS = {
    "TITLE": "GetStart PDV API",
    "VERSION": "1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN",""),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
)

# =============================
# 🧱 Templates
# =============================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "pdv-default",
    }
}

REST_FRAMEWORK.update({
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "60/min"},  # prod
})

import logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "class": "pythonjsonlogger.json.JsonFormatter",
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "INFO",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "pdv.fiscal": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

#"CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60"))
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 63072000
SECURE_FRAME_DENY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

