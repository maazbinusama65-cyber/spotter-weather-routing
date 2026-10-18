"""In-memory stand-ins for the routing and weather providers."""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta

from api.providers.types import Place, ProviderError, RouteNotFound, RouteOption
from engine.forecast import HourlyForecast
from engine.geo import LatLon, cumulative_miles
from engine.sampling import RouteGeometry

WeatherFn = Callable[[float, float, datetime], tuple[float, float, float]]


def calm(lat: float, lon: float, when: datetime) -> tuple[float, float, float]:
    return 5.0, 0.0, 0.0


class FakeRouting:
    """Routes are straight lines between the waypoints, driven at a constant speed."""

    def __init__(
        self,
        speed_mph: float = 50.0,
        fail_via: bool = False,
        fail_base: bool = False,
        via_error: Exception | None = None,
        base_error: Exception | None = None,
    ):
        self.speed_mph = speed_mph
        self.fail_via = fail_via
        self.fail_base = fail_base
        self.via_error = via_error
        self.base_error = base_error
        self.calls: list[tuple[LatLon, ...]] = []

    def route(self, waypoints: Sequence[LatLon]) -> RouteOption:
        self.calls.append(tuple(waypoints))
        if len(waypoints) > 2 and self.via_error:
            raise self.via_error
        if len(waypoints) == 2 and self.base_error:
            raise self.base_error
        if len(waypoints) > 2 and self.fail_via:
            raise RouteNotFound("no route through that point")
        if len(waypoints) == 2 and self.fail_base:
            raise ProviderError("Routing service is unavailable")
        coordinates = tuple(waypoints)
        miles = cumulative_miles(coordinates)[-1]
        geometry = RouteGeometry(coordinates, duration_s=miles / self.speed_mph * 3600)
        return RouteOption(geometry=geometry, via="Fake Rd")

    def geocode(self, text: str) -> list[Place]:
        return [Place(label=f"{text}, Testville", lat=1.0, lon=2.0)]


class FakeWeather:
    def __init__(self, fn: WeatherFn = calm, timezone: str = "UTC", limit_hours: int | None = None):
        self.fn = fn
        self.timezone = timezone
        self.limit_hours = limit_hours
        self.calls: list[tuple[list[LatLon], date, date]] = []

    def forecasts(self, points: Sequence[LatLon], start: date, end: date) -> list[HourlyForecast]:
        self.calls.append((list(points), start, end))
        first = datetime(start.year, start.month, start.day, tzinfo=UTC)
        hours = ((end - start).days + 1) * 24
        if self.limit_hours is not None:
            hours = min(hours, self.limit_hours)
        forecasts = []
        for lat, lon in points:
            times = tuple(first + timedelta(hours=h) for h in range(hours))
            values = [self.fn(lat, lon, t) for t in times]
            forecasts.append(
                HourlyForecast(
                    times=times,
                    wind_mph=tuple(v[0] for v in values),
                    rain_in_hr=tuple(v[1] for v in values),
                    snow_in_hr=tuple(v[2] for v in values),
                )
            )
        return forecasts

    def timezone_name(self, point: LatLon) -> str:
        return self.timezone
