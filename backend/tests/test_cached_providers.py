"""Cache decorators that protect the free-tier quotas of the routing and weather APIs."""

from datetime import date

import pytest
from django.core.cache.backends.locmem import LocMemCache

from api.providers.cached import CachedRouting, CachedWeather
from api.providers.types import ProviderError
from tests.fakes import FakeRouting, FakeWeather

DAY = date(2026, 11, 2)
NEXT_DAY = date(2026, 11, 3)


@pytest.fixture
def cache():
    store = LocMemCache("test", {})
    yield store
    store.clear()


def test_identical_forecast_requests_hit_the_provider_once(cache):
    inner = FakeWeather()
    weather = CachedWeather(inner, cache)

    first = weather.forecasts([(1.0, 2.0), (3.0, 4.0)], DAY, DAY)
    second = weather.forecasts([(1.0, 2.0), (3.0, 4.0)], DAY, DAY)

    assert len(inner.calls) == 1
    assert first == second


def test_only_uncached_points_are_fetched_and_order_is_preserved(cache):
    inner = FakeWeather(lambda lat, lon, when: (lat, 0.0, 0.0))
    weather = CachedWeather(inner, cache)
    weather.forecasts([(1.0, 2.0)], DAY, DAY)

    result = weather.forecasts([(3.0, 4.0), (1.0, 2.0), (5.0, 6.0)], DAY, DAY)

    assert inner.calls[1][0] == [(3.0, 4.0), (5.0, 6.0)]
    assert [f.wind_mph[0] for f in result] == [3.0, 1.0, 5.0]


def test_a_different_date_range_is_a_different_cache_entry(cache):
    inner = FakeWeather()
    weather = CachedWeather(inner, cache)

    weather.forecasts([(1.0, 2.0)], DAY, DAY)
    weather.forecasts([(1.0, 2.0)], DAY, NEXT_DAY)

    assert len(inner.calls) == 2


def test_provider_errors_are_not_cached(cache):
    class Flaky(FakeWeather):
        def forecasts(self, points, start, end):
            if not self.calls:
                self.calls.append(None)
                raise ProviderError("Weather service is busy")
            return super().forecasts(points, start, end)

    weather = CachedWeather(Flaky(), cache)

    with pytest.raises(ProviderError):
        weather.forecasts([(1.0, 2.0)], DAY, DAY)
    assert len(weather.forecasts([(1.0, 2.0)], DAY, DAY)) == 1


def test_timezone_lookups_are_cached_per_area(cache):
    class CountingWeather(FakeWeather):
        lookups = 0

        def timezone_name(self, point):
            CountingWeather.lookups += 1
            return "America/Denver"

    weather = CachedWeather(CountingWeather(), cache)

    assert weather.timezone_name((39.74, -104.99)) == "America/Denver"
    assert weather.timezone_name((39.74, -104.99)) == "America/Denver"
    assert CountingWeather.lookups == 1


def test_identical_routes_are_requested_once(cache):
    inner = FakeRouting()
    routing = CachedRouting(inner, cache)
    waypoints = [(1.0, 2.0), (1.0, 4.0)]

    first = routing.route(waypoints)
    second = routing.route(waypoints)

    assert len(inner.calls) == 1
    assert first == second


def test_route_failures_are_not_cached(cache):
    inner = FakeRouting(fail_base=True)
    routing = CachedRouting(inner, cache)

    for _ in range(2):
        with pytest.raises(ProviderError):
            routing.route([(1.0, 2.0), (1.0, 4.0)])

    assert len(inner.calls) == 2


def test_geocoding_is_cached_ignoring_case_and_spacing(cache):
    inner = FakeRouting()
    inner_calls = []
    original = inner.geocode
    inner.geocode = lambda text: inner_calls.append(text) or original(text)
    routing = CachedRouting(inner, cache)

    routing.geocode("Denver")
    routing.geocode("  denver ")

    assert len(inner_calls) == 1


def test_cache_keys_are_safe_for_memcached_style_backends(cache):
    import warnings

    routing = CachedRouting(FakeRouting(), cache)

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # Django warns (CacheKeyWarning) on spaces in keys
        routing.geocode("Denver, CO")
