import pytest
from django.core.cache import caches


@pytest.fixture(autouse=True)
def clear_caches():
    """Throttle counters and cached lookups live in process memory; keep tests independent."""
    for cache in caches.all():
        cache.clear()
    yield
    for cache in caches.all():
        cache.clear()
