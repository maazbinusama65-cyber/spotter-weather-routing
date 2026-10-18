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
    trailing = max((_trailing_unknown(point.levels) for point in points), default=0)
    if trailing:
        plural = "s" if trailing != 1 else ""
        return [
            f"The weather forecast does not cover the last {trailing} hour{plural} "
            "of this window; those hours are shown as unknown"
        ]
    if any(UNKNOWN_LEVEL in point.levels for point in points):
        return ["Weather data is missing for some hours; they are shown as unknown"]
    return []


def _trailing_unknown(levels: str) -> int:
    return len(levels) - len(levels.rstrip(UNKNOWN_LEVEL))
