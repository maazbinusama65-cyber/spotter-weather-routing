"""Cache decorators for the providers.

They stop repeated requests from spending free-tier quota (ORS 2,000 directions/day) and
keep warm requests fast. Failures are never cached. Backed by Django's cache framework,
so moving from in-memory to Redis is a settings change.
"""

import hashlib
from collections.abc import Sequence
from datetime import date

from engine.forecast import HourlyForecast
from engine.geo import LatLon

from .types import Place, RouteOption, RoutingProvider, WeatherProvider

FORECAST_TTL_SECONDS = 15 * 60  # forecasts refresh hourly
ROUTE_TTL_SECONDS = 60 * 60
GEOCODE_TTL_SECONDS = 24 * 60 * 60
TIMEZONE_TTL_SECONDS = 7 * 24 * 60 * 60
_TIMEZONE_AREA_DECIMALS = 1


def _point_key(point: LatLon) -> str:
    return f"{round(point[0], 4)},{round(point[1], 4)}"


class CachedWeather:
    def __init__(self, inner: WeatherProvider, cache, ttl: int = FORECAST_TTL_SECONDS) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl

    def forecasts(self, points: Sequence[LatLon], start: date, end: date) -> list[HourlyForecast]:
        keys = [f"om:{_point_key(p)}:{start}:{end}" for p in points]
        cached = self._cache.get_many(keys)
        missing = [p for p, key in zip(points, keys, strict=True) if key not in cached]
        if missing:
            fetched = self._inner.forecasts(missing, start, end)
            fresh = {
                f"om:{_point_key(p)}:{start}:{end}": forecast
                for p, forecast in zip(missing, fetched, strict=True)
            }
            self._cache.set_many(fresh, self._ttl)
            cached = {**cached, **fresh}
        return [cached[key] for key in keys]

    def timezone_name(self, point: LatLon) -> str:
        lat, lon = (round(v, _TIMEZONE_AREA_DECIMALS) for v in point)
        key = f"tz:{lat},{lon}"
        name = self._cache.get(key)
        if name is None:
            name = self._inner.timezone_name(point)
            self._cache.set(key, name, TIMEZONE_TTL_SECONDS)
        return name


class CachedRouting:
    def __init__(self, inner: RoutingProvider, cache) -> None:
        self._inner = inner
        self._cache = cache

    def route(self, waypoints: Sequence[LatLon]) -> RouteOption:
        key = "route:" + "|".join(_point_key(p) for p in waypoints)
        option = self._cache.get(key)
        if option is None:
            option = self._inner.route(waypoints)
            self._cache.set(key, option, ROUTE_TTL_SECONDS)
        return option

    def geocode(self, text: str) -> list[Place]:
        normalized = " ".join(text.lower().split())
        key = "geo:" + hashlib.sha1(normalized.encode()).hexdigest()  # no spaces or odd characters
        places = self._cache.get(key)
        if places is None:
            places = self._inner.geocode(text)
            self._cache.set(key, places, GEOCODE_TTL_SECONDS)
        return places
