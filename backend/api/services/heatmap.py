"""Weather heatmap: a corridor grid with a 0-48 hour risk series at every point."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from api.providers.types import RoutingProvider, WeatherProvider
from engine.corridor import corridor_points
from engine.heat import UNKNOWN_LEVEL, hourly_levels

from .trip import TripRequest, find_routes, last_forecast_day, resolve_trip_start

HEATMAP_HOURS = 49  # forecast hours 0 to 48 from departure


@dataclass(frozen=True)
class HeatPoint:
    lat: float
    lon: float
    levels: str  # one character per hour: risk level 0-4, or "-" when unknown


@dataclass(frozen=True)
class Heatmap:
    start: datetime  # UTC, the departure rounded down to the hour
    hours: int
    timezone: str
    points: tuple[HeatPoint, ...]
    warnings: list[str]


def build_heatmap(
    request: TripRequest,
    routing: RoutingProvider,
    weather: WeatherProvider,
    now: datetime | None = None,
) -> Heatmap:
    now = now or datetime.now(UTC)
    departure_utc, timezone = resolve_trip_start(request, weather, now)

    options = find_routes(request, routing, warnings=[])
    cells = corridor_points([option.geometry for option in options])

    start = departure_utc.replace(minute=0, second=0, microsecond=0)
    final_day = last_forecast_day(now)
    first_day = min(start.date(), final_day)
    end_day = min((start + timedelta(hours=HEATMAP_HOURS)).date(), final_day)
    forecasts = weather.forecasts(cells, first_day, end_day)

    points = tuple(
        HeatPoint(lat, lon, hourly_levels(forecast, start, HEATMAP_HOURS, request.load_lb))
        for (lat, lon), forecast in zip(cells, forecasts, strict=True)
    )
    return Heatmap(start, HEATMAP_HOURS, timezone, points, _warnings(points))


def _warnings(points: tuple[HeatPoint, ...]) -> list[str]:
    missing = max((point.levels.count(UNKNOWN_LEVEL) for point in points), default=0)
    if missing == 0:
        return []
    return [
        f"The weather forecast does not cover the last {missing} hour"
        f"{'s' if missing != 1 else ''} of this window; those hours are shown as unknown"
    ]
