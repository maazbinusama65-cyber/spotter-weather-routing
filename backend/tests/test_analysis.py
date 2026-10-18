"""Turning checkpoints plus weather into per-route mile totals and an average risk."""

from datetime import UTC, datetime

import pytest

from engine.analysis import evaluate_checkpoints, summarize_route
from engine.geo import MILES_PER_DEGREE_EQUATOR
from engine.risk import RiskLevel, WeatherSample
from engine.sampling import RouteGeometry, sample_checkpoints

DEPARTURE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
LIGHT_LOAD = 10_000

CALM = WeatherSample(5, 0, 0)
MODERATE = WeatherSample(28, 0, 0)
HIGH = WeatherSample(38, 0, 0)
SEVERE = WeatherSample(48, 0, 0)
NO_TRAVEL = WeatherSample(60, 0, 0)


def hundred_mile_route():
    degrees = 100 / MILES_PER_DEGREE_EQUATOR
    return RouteGeometry(coordinates=((0, 0), (0, degrees)), duration_s=7200)


def test_miles_are_bucketed_by_checkpoint_level():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 25, DEPARTURE)  # owns 12.5, 25, 25, 25, 12.5
    samples = [CALM, MODERATE, HIGH, SEVERE, NO_TRAVEL]

    analyses = evaluate_checkpoints(checkpoints, samples, LIGHT_LOAD)
    summary = summarize_route("r1", "Route 1", route.duration_s, analyses)

    assert summary.low_miles == pytest.approx(12.5)
    assert summary.moderate_miles == pytest.approx(25)
    assert summary.high_miles == pytest.approx(25)
    assert summary.severe_miles == pytest.approx(25)
    assert summary.no_travel_miles == pytest.approx(12.5)
    assert summary.unknown_miles == 0
    assert summary.distance_mi == pytest.approx(100)
    assert summary.max_level == RiskLevel.NO_TRAVEL
    assert summary.duration_s == 7200


def test_severe_miles_do_not_also_count_as_high_miles():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 50, DEPARTURE)

    analyses = evaluate_checkpoints(checkpoints, [SEVERE, SEVERE, SEVERE], LIGHT_LOAD)
    summary = summarize_route("r1", "Route 1", route.duration_s, analyses)

    assert summary.severe_miles == pytest.approx(100)
    assert summary.high_miles == 0


def test_average_risk_is_weighted_by_miles_not_checkpoint_count():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 25, DEPARTURE)
    samples = [CALM, MODERATE, HIGH, SEVERE, NO_TRAVEL]

    analyses = evaluate_checkpoints(checkpoints, samples, LIGHT_LOAD)
    summary = summarize_route("r1", "Route 1", route.duration_s, analyses)

    expected = (0 * 12.5 + 1 * 25 + 2 * 25 + 3 * 25 + 4 * 12.5) / 100
    assert summary.avg_risk == pytest.approx(expected)


def test_load_changes_the_outcome_for_the_same_weather():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 50, DEPARTURE)
    breezy = [WeatherSample(40, 0, 0)] * 3  # high on its own, severe for a heavy load

    light = summarize_route("r", "R", 0, evaluate_checkpoints(checkpoints, breezy, 20_000))
    heavy = summarize_route("r", "R", 0, evaluate_checkpoints(checkpoints, breezy, 45_000))

    assert (light.high_miles, light.severe_miles) == (pytest.approx(100), 0)
    assert (heavy.high_miles, heavy.severe_miles) == (0, pytest.approx(100))


def test_unknown_weather_is_tracked_separately_and_excluded_from_average():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 50, DEPARTURE)  # owns 25, 50, 25

    analyses = evaluate_checkpoints(checkpoints, [CALM, None, SEVERE], LIGHT_LOAD)
    summary = summarize_route("r1", "Route 1", route.duration_s, analyses)

    assert summary.unknown_miles == pytest.approx(50)
    assert summary.avg_risk == pytest.approx((0 * 25 + 3 * 25) / 50)
    assert analyses[1].risk is None


def test_route_with_no_known_weather_has_zero_average_and_all_unknown():
    route = hundred_mile_route()
    checkpoints = sample_checkpoints(route, 50, DEPARTURE)

    analyses = evaluate_checkpoints(checkpoints, [None, None, None], LIGHT_LOAD)
    summary = summarize_route("r1", "Route 1", route.duration_s, analyses)

    assert summary.avg_risk == 0
    assert summary.unknown_miles == pytest.approx(100)


def test_sample_count_must_match_checkpoint_count():
    checkpoints = sample_checkpoints(hundred_mile_route(), 50, DEPARTURE)

    with pytest.raises(ValueError, match="sample"):
        evaluate_checkpoints(checkpoints, [CALM], LIGHT_LOAD)


def test_checkpoint_analysis_keeps_checkpoint_weather_and_risk_together():
    checkpoints = sample_checkpoints(hundred_mile_route(), 50, DEPARTURE)

    analyses = evaluate_checkpoints(checkpoints, [CALM, SEVERE, CALM], LIGHT_LOAD)

    middle = analyses[1]
    assert middle.checkpoint is checkpoints[1]
    assert middle.weather == SEVERE
    assert middle.risk.level == RiskLevel.SEVERE
