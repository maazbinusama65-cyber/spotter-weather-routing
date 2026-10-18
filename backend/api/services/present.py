"""Turn a TripAnalysis into the JSON the frontend consumes."""

from datetime import datetime

from engine.analysis import CheckpointAnalysis, RouteSummary
from engine.geo import simplify_polyline
from engine.levels import RiskLevel
from engine.thresholds import RULESET_VERSION

from .trip import AnalyzedRoute, TripAnalysis

MAP_SIMPLIFY_TOLERANCE_DEGREES = 0.0005  # about 50 m; plenty for drawing on a map
COORDINATE_DECIMALS = 5


def present_analysis(analysis: TripAnalysis) -> dict:
    request = analysis.request
    return {
        "ruleset_version": RULESET_VERSION,
        "risk_levels": [{"value": int(level), "label": level.label} for level in RiskLevel],
        "timezone": analysis.timezone,
        "departure": _iso(analysis.departure_utc),
        "origin": {"lat": request.origin[0], "lon": request.origin[1]},
        "destination": {"lat": request.destination[0], "lon": request.destination[1]},
        "load_lb": request.load_lb,
        "interval_miles": request.interval_miles,
        "routes": [_route(route) for route in analysis.routes],
        "recommendation": {
            "route_id": analysis.recommendation.best_route_id,
            "ranking": list(analysis.recommendation.ranking),
            "reason": analysis.recommendation.reason,
            "all_blocked": analysis.recommendation.all_blocked,
        },
        "warnings": analysis.warnings,
    }


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _route(route: AnalyzedRoute) -> dict:
    summary = route.summary
    return {
        "id": route.route_id,
        "label": route.label,
        "via": route.option.via,
        "distance_mi": round(summary.distance_mi, 1),
        "duration_s": round(summary.duration_s),
        "arrival": _iso(route.checkpoints[-1].checkpoint.eta),
        "geometry": _geometry(route),
        "summary": _summary(summary),
        "checkpoints": [_checkpoint(analysis) for analysis in route.checkpoints],
    }


def _geometry(route: AnalyzedRoute) -> dict:
    simplified = simplify_polyline(
        route.option.geometry.coordinates, MAP_SIMPLIFY_TOLERANCE_DEGREES
    )
    return {
        "type": "LineString",
        "coordinates": [
            [round(lon, COORDINATE_DECIMALS), round(lat, COORDINATE_DECIMALS)]
            for lat, lon in simplified
        ],
    }


def _summary(summary: RouteSummary) -> dict:
    return {
        "no_travel_miles": round(summary.no_travel_miles, 1),
        "severe_miles": round(summary.severe_miles, 1),
        "high_miles": round(summary.high_miles, 1),
        "moderate_miles": round(summary.moderate_miles, 1),
        "low_miles": round(summary.low_miles, 1),
        "unknown_miles": round(summary.unknown_miles, 1),
        "avg_risk": round(summary.avg_risk, 2),
        "max_level": int(summary.max_level),
        "max_level_label": summary.max_level.label,
    }


def _checkpoint(analysis: CheckpointAnalysis) -> dict:
    checkpoint, weather, risk = analysis.checkpoint, analysis.weather, analysis.risk
    return {
        "index": checkpoint.index,
        "distance_mi": round(checkpoint.distance_mi, 1),
        "segment_miles": round(checkpoint.segment_miles, 1),
        "lat": round(checkpoint.lat, COORDINATE_DECIMALS),
        "lon": round(checkpoint.lon, COORDINATE_DECIMALS),
        "eta": _iso(checkpoint.eta),
        "wind_mph": None if weather is None else round(weather.wind_mph, 1),
        "rain_in_hr": None if weather is None else round(weather.rain_in_hr, 3),
        "snow_in_hr": None if weather is None else round(weather.snow_in_hr, 3),
        "level": None if risk is None else int(risk.level),
        "level_label": "Unknown" if risk is None else risk.level.label,
        "driver": None if risk is None else risk.driver,
        "load_escalated": False if risk is None else risk.load_escalated,
        "reason": "Weather unavailable" if risk is None else risk.reason,
    }
