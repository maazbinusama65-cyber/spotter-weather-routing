from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from engine.forecast import HourlyForecast
from engine.geo import LatLon
from engine.sampling import RouteGeometry


class ProviderError(Exception):
    """An upstream service failed. The message is safe to show to the user."""


class RouteNotFound(ProviderError):
    """The routing provider could not find a route for these waypoints."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteOption:
    geometry: RouteGeometry
    via: str  # main roads, e.g. "I 80, I 76"


class RoutingProvider(Protocol):
    def route(self, waypoints: Sequence[LatLon]) -> RouteOption: ...

    def geocode(self, text: str) -> list[Place]: ...


class WeatherProvider(Protocol):
    def forecasts(self, points: Sequence[LatLon], start: date, end: date) -> list[HourlyForecast]:
        """One forecast per point, same order, covering start..end inclusive (UTC dates)."""
        ...

    def timezone_name(self, point: LatLon) -> str: ...
