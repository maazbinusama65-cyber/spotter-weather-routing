"""Analyze a trip: find routes, sample weather at each ETA, score risk, recommend one."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api.providers.types import (
    ProviderError,
    RouteNotFound,
    RouteOption,
    RoutingProvider,
    WeatherProvider,
)
from engine.analysis import CheckpointAnalysis, RouteSummary, evaluate_checkpoints, summarize_route
from engine.candidates import generate_via_points, select_distinct_routes
from engine.forecast import HourlyForecast, sample_at
from engine.geo import LatLon, cumulative_miles, haversine_miles
from engine.ranking import Recommendation, rank_routes
from engine.sampling import Checkpoint, sample_checkpoints

logger = logging.getLogger(__name__)

MAX_ROUTES = 3
VIA_FRACTIONS = (0.35, 0.65)
VIA_OFFSET_SHARE = 0.12  # of route length, clamped below
VIA_OFFSET_MIN_MILES = 10.0
VIA_OFFSET_MAX_MILES = 60.0
ROUTING_WORKERS = 4
WEATHER_CELL_DECIMALS = 1  # 0.1 degree cells, roughly 7 miles
FORECAST_DAYS_AHEAD = 15
PAST_DEPARTURE_ALLOWED = timedelta(hours=24)
MIN_TRIP_MILES = 0.5
MAX_TRIP_MILES = 3500  # coast to coast is about 2,900

Cell = tuple[float, float]


class TripValidationError(ValueError):
    """The request cannot be analyzed as given; the message is safe to show the user."""


@dataclass(frozen=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    departure: datetime  # naive means local time at the origin
    load_lb: float
    interval_miles: float


@dataclass(frozen=True)
class AnalyzedRoute:
    route_id: str
    label: str
    option: RouteOption
    checkpoints: tuple[CheckpointAnalysis, ...]
    summary: RouteSummary


@dataclass(frozen=True)
class TripAnalysis:
    request: TripRequest
    departure_utc: datetime
    timezone: str
    routes: tuple[AnalyzedRoute, ...]
    recommendation: Recommendation
    warnings: list[str]


def analyze_trip(
    request: TripRequest,
    routing: RoutingProvider,
    weather: WeatherProvider,
    now: datetime | None = None,
) -> TripAnalysis:
    now = now or datetime.now(UTC)
    departure_utc, timezone = resolve_trip_start(request, weather, now)

    warnings: list[str] = []
    options = find_routes(request, routing, warnings)
    checkpoints = [
        sample_checkpoints(option.geometry, request.interval_miles, departure_utc)
        for option in options
    ]
    forecasts = _fetch_forecasts(checkpoints, weather, now)

    routes = []
    for number, (option, route_checkpoints) in enumerate(zip(options, checkpoints, strict=True), 1):
        samples = [sample_at(forecasts[_cell(cp.lat, cp.lon)], cp.eta) for cp in route_checkpoints]
        analyses = evaluate_checkpoints(route_checkpoints, samples, request.load_lb)
        label = f"Route {number}"
        summary = summarize_route(f"r{number}", label, option.geometry.duration_s, analyses)
        routes.append(AnalyzedRoute(f"r{number}", label, option, analyses, summary))

    recommendation = rank_routes([route.summary for route in routes])
    warnings.extend(_weather_warnings(routes, recommendation))
    return TripAnalysis(request, departure_utc, timezone, tuple(routes), recommendation, warnings)


def resolve_trip_start(
    request: TripRequest, weather: WeatherProvider, now: datetime
) -> tuple[datetime, str]:
    """Check the trip's basics; return the departure in UTC and the origin's time zone."""
    if haversine_miles(request.origin, request.destination) < MIN_TRIP_MILES:
        raise TripValidationError("Origin and destination are the same place")
    departure_utc, timezone = _resolve_departure(
        request.departure, weather.timezone_name(request.origin)
    )
    _check_departure_window(departure_utc, now)
    return departure_utc, timezone


def last_forecast_day(now: datetime) -> date:
    return (now + timedelta(days=FORECAST_DAYS_AHEAD)).date()


def _resolve_departure(departure: datetime, timezone: str) -> tuple[datetime, str]:
    """Departure in UTC and the time zone name used to read a naive departure."""
    if departure.tzinfo is None:
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("Unknown time zone %r from the weather service; using UTC", timezone)
            zone, timezone = UTC, "UTC"
        departure = departure.replace(tzinfo=zone)
    try:
        return departure.astimezone(UTC), timezone
    except OverflowError as error:
        raise TripValidationError("Check the departure date and time") from error


def _check_departure_window(departure_utc: datetime, now: datetime) -> None:
    if departure_utc < now - PAST_DEPARTURE_ALLOWED:
        raise TripValidationError("Departure is too far in the past")
    if departure_utc > now + timedelta(days=FORECAST_DAYS_AHEAD):
        raise TripValidationError(
            f"Departure is beyond the {FORECAST_DAYS_AHEAD}-day weather forecast"
        )


def find_routes(
    request: TripRequest, routing: RoutingProvider, warnings: list[str]
) -> list[RouteOption]:
    base = routing.route([request.origin, request.destination])
    base_miles = cumulative_miles(base.geometry.coordinates)[-1]
    if base_miles > MAX_TRIP_MILES:
        raise TripValidationError(f"Trip is longer than {MAX_TRIP_MILES:,} miles")
    offset = min(VIA_OFFSET_MAX_MILES, max(VIA_OFFSET_MIN_MILES, VIA_OFFSET_SHARE * base_miles))
    via_points = generate_via_points(base.geometry.coordinates, VIA_FRACTIONS, offset)

    failures: list[ProviderError] = []

    def through(via: LatLon) -> RouteOption | None:
        try:
            return routing.route([request.origin, via, request.destination])
        except RouteNotFound:
            logger.info("No route through alternative via point %s", via)
        except ProviderError as error:
            logger.warning("Alternative route lookup failed (%s): %s", type(error).__name__, error)
            failures.append(error)
        return None

    with ThreadPoolExecutor(max_workers=ROUTING_WORKERS) as pool:
        alternatives = [option for option in pool.map(through, via_points) if option is not None]

    candidates = [base, *alternatives]
    chosen = select_distinct_routes([c.geometry for c in candidates], max_routes=MAX_ROUTES)
    if failures:
        plural = "s" if len(failures) != 1 else ""
        warnings.append(
            f"{len(failures)} alternative route lookup{plural} failed ({failures[0]}); "
            "fewer options are shown"
        )
    elif len(chosen) < MAX_ROUTES:
        warnings.append(
            f"Only {len(chosen)} distinct route{'s' if len(chosen) != 1 else ''} "
            "found; no further alternatives could be generated for this trip"
        )
    return [candidates[i] for i in chosen]


def _cell(lat: float, lon: float) -> Cell:
    return round(lat, WEATHER_CELL_DECIMALS), round(lon, WEATHER_CELL_DECIMALS)


def _fetch_forecasts(
    checkpoints: list[tuple[Checkpoint, ...]], weather: WeatherProvider, now: datetime
) -> dict[Cell, HourlyForecast]:
    all_checkpoints = [cp for route in checkpoints for cp in route]
    cells = sorted({_cell(cp.lat, cp.lon) for cp in all_checkpoints})
    etas = [cp.eta for cp in all_checkpoints]
    # Never ask beyond the forecast; ETAs past it simply have no weather (unknown miles).
    final_day = last_forecast_day(now)
    start = min(min(etas).date(), final_day)
    end = min((max(etas) + timedelta(hours=1)).date(), final_day)
    return dict(zip(cells, weather.forecasts(cells, start, end), strict=True))


def _weather_warnings(routes: list[AnalyzedRoute], recommendation: Recommendation) -> list[str]:
    warnings = []
    unknown = max(route.summary.unknown_miles for route in routes)
    if unknown > 0:
        warnings.append(
            f"Weather data is unavailable for up to {unknown:.0f} mi of the trip "
            "(beyond the forecast); those miles are not scored"
        )
    if recommendation.all_blocked:
        warnings.append(
            "Every route has No Travel conditions; the least affected route is recommended"
        )
    return warnings
