"""Production settings: fail-safe defaults, hostnames, and security headers."""

import runpy
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient

SETTINGS_FILE = str(Path(__file__).parent.parent / "config" / "settings.py")

ENV_KEYS = (
    "DJANGO_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "RENDER",
    "RENDER_EXTERNAL_HOSTNAME",
    "DJANGO_NUM_PROXIES",
)


@pytest.fixture
def load_settings(monkeypatch):
    """Evaluate config/settings.py under a controlled environment, without touching Django."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    def load(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return runpy.run_path(SETTINGS_FILE)

    return load


def test_development_is_the_default_locally(load_settings):
    config = load_settings()

    assert config["DEBUG"] is True
    assert config["IS_PRODUCTION"] is False
    assert config["REST_FRAMEWORK"]["NUM_PROXIES"] == 0


def test_production_requires_a_secret_key(load_settings):
    with pytest.raises(ImproperlyConfigured):
        load_settings(DJANGO_ENV="production")


def test_a_render_deploy_is_production_even_without_django_env(load_settings):
    with pytest.raises(ImproperlyConfigured):
        load_settings(RENDER="true")


def test_production_turns_off_debug_and_trusts_one_proxy(load_settings):
    config = load_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 50)

    assert config["DEBUG"] is False
    assert config["REST_FRAMEWORK"]["NUM_PROXIES"] == 1
    assert config["SECURE_SSL_REDIRECT"] is True
    assert config["SECURE_HSTS_SECONDS"] > 0


def test_the_render_hostname_is_allowed_automatically(load_settings):
    config = load_settings(
        DJANGO_ENV="production",
        DJANGO_SECRET_KEY="x" * 50,
        RENDER_EXTERNAL_HOSTNAME="stormline.onrender.com",
    )

    assert "stormline.onrender.com" in config["ALLOWED_HOSTS"]


def test_the_health_check_is_exempt_from_the_https_redirect(load_settings):
    config = load_settings(DJANGO_ENV="production", DJANGO_SECRET_KEY="x" * 50)

    assert any("api/health" in pattern for pattern in config["SECURE_REDIRECT_EXEMPT"])


def test_responses_carry_a_content_security_policy_that_still_allows_the_map():
    response = APIClient().get("/api/health")

    policy = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "worker-src 'self' blob:" in policy
    assert "connect-src 'self' https://tiles.openfreemap.org" in policy
    assert "'unsafe-eval'" not in policy


def test_responses_forbid_content_type_sniffing_and_framing():
    response = APIClient().get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
