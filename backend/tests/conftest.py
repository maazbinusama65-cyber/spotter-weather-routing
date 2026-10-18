import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_default_cache():
    """Throttle counters live in the default cache; keep tests independent."""
    cache.clear()
    yield
    cache.clear()
