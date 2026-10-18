"""Django settings. Stateless API: no database, sessions, or auth."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env")

ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
# Fail safe: a Render deploy is production even if DJANGO_ENV was forgotten.
IS_PRODUCTION = ENVIRONMENT == "production" or os.getenv("RENDER") == "true"
DEBUG = not IS_PRODUCTION

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]
# Render tells the service its public hostname; allow it without extra configuration.
if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Before WhiteNoise, so the policy is also added to the static site it serves.
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES: dict = {}

# In-memory cache is enough for a single instance. Swapping in Redis later is
# a settings change only.
_LOCMEM = "django.core.cache.backends.locmem.LocMemCache"
CACHES = {
    # forecasts, timezones: many small entries
    "default": {"BACKEND": _LOCMEM, "LOCATION": "default", "OPTIONS": {"MAX_ENTRIES": 5000}},
    # routes hold long polylines, so keep few of them and do not let them evict anything else
    "routes": {"BACKEND": _LOCMEM, "LOCATION": "routes", "OPTIONS": {"MAX_ENTRIES": 100}},
    # rate-limit counters must not be evictable by cache churn
    "throttle": {"BACKEND": _LOCMEM, "LOCATION": "throttle", "OPTIONS": {"MAX_ENTRIES": 10000}},
}
# Counters are per process, so run a single gunicorn worker with threads (see Dockerfile).

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "analyze": "10/min",
        "heatmap": "10/min",
        "geocode": "60/min",
    },
    "EXCEPTION_HANDLER": "api.errors.api_exception_handler",
    # Trusted proxy hops in front of Django; stops clients spoofing X-Forwarded-For.
    "NUM_PROXIES": int(os.getenv("DJANGO_NUM_PROXIES", "1" if IS_PRODUCTION else "0")),
}

# Content Security Policy: only our own scripts run. The map needs its tile host, blob
# workers and inline styles (MapLibre popups and React style attributes).
_TILE_HOST = "https://tiles.openfreemap.org"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "blob:", _TILE_HOST],
    "font-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF, _TILE_HOST],
    "worker-src": [CSP.SELF, "blob:"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
X_FRAME_OPTIONS = "DENY"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The built React app is served from the site root by WhiteNoise.
WHITENOISE_ROOT = REPO_ROOT / "frontend" / "dist"
WHITENOISE_INDEX_FILE = True

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "10"))

if IS_PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = 31536000
    # The host's health probe calls over plain HTTP inside the network.
    SECURE_REDIRECT_EXEMPT = [r"^api/health$"]

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "api": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "WARNING"},
    },
}
