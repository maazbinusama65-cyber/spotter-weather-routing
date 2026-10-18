"""Trip orchestration: routes, ETA-based weather, risk, ranking, and validation."""

from datetime import UTC, datetime, timedelta

import pytest

from api.providers.types import ProviderError
from api.services.trip import TripRequest, TripValidationError, analyze_trip
from engine.geo import MILES_PER_DEGREE_EQUATOR
from engine.risk import RiskLevel
from tests.fakes import FakeRouting, FakeWeather, calm

DEG = 1 / MILES_PER_DEGREE_EQUATOR
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
DEPARTURE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
ORIGIN = (0.0, 0.0)
DESTINATION = (0.0, 200 * DEG)  # 200 miles due east


def request(**overrides) -> TripRequest:
    fields = dict(
        origin=ORIGIN,
        destination=DESTINATION,
        departure=DEPARTURE,
        load_lb=20_000,
        interval_miles=50,
    )
    return TripRequest(**{**fields, **overrides})


def run(req=None, routing=None, weather=None):
    return analyze_trip(req or request(), routing or FakeRouting(), weather or FakeWeather(), NOW)


def test_returns_three_distinct_routes_with_checkpoints_at_the_chosen_interval():
    analysis = run()

    assert [r.route_id for r in analysis.routes] == ["r1", "r2", "r3"]
    base = analysis.routes[0]
    assert [round(c.checkpoint.distance_mi) for c in base.checkpoints] == [0, 50, 100, 150, 200]
    assert analysis.recommendation.best_route_id in {"r1", "r2", "r3"}
    assert analysis.warnings == []


def test_routes_get_distinct_labels_and_main_roads():
    analysis = run()

    assert [r.label for r in analysis.routes] == ["Route 1", "Route 2", "Route 3"]
    assert all(r.option.via == "Fake Rd" for r in analysis.routes)


def test_recommendation_avoids_a_storm_sitting_on_the_direct_route():
    def storm_on_equator(lat, lon, when):
        return (48.0, 0.0, 0.0) if abs(lat) < 0.1 else (5.0, 0.0, 0.0)

    analysis = run(weather=FakeWeather(storm_on_equator))

    by_id = {r.route_id: r for r in analysis.routes}
    best = by_id[analysis.recommendation.best_route_id]
    assert analysis.recommendation.best_route_id != "r1"
    assert best.summary.severe_miles < by_id["r1"].summary.severe_miles
    assert by_id["r1"].summary.severe_miles == pytest.approx(200, abs=1)


def test_weather_is_taken_at_each_checkpoints_eta_not_at_departure():
    def storm_after_ten(lat, lon, when):
        return (
            (48.0, 0.0, 0.0)
            if when >= datetime(2026, 11, 2, 10, tzinfo=UTC)
            else calm(lat, lon, when)
        )

    analysis = run(weather=FakeWeather(storm_after_ten))

    # 50 mph: checkpoints reached at 08:00, 09:00, 10:00, 11:00, 12:00
    levels = [c.risk.level for c in analysis.routes[0].checkpoints]
    assert levels == [RiskLevel.LOW, RiskLevel.LOW] + [RiskLevel.SEVERE] * 3


def test_naive_departure_is_read_in_the_origin_timezone():
    weather = FakeWeather(timezone="America/Chicago")

    analysis = run(request(departure=datetime(2026, 11, 2, 8, 0)), weather=weather)

    assert analysis.timezone == "America/Chicago"
    assert analysis.departure_utc == datetime(2026, 11, 2, 14, 0, tzinfo=UTC)  # CST is UTC-6
    assert analysis.routes[0].checkpoints[0].checkpoint.eta == analysis.departure_utc


def test_aware_departure_is_respected_as_given():
    from datetime import timezone

    mountain = timezone(timedelta(hours=-7))

    analysis = run(request(departure=datetime(2026, 11, 2, 8, 0, tzinfo=mountain)))

    assert analysis.departure_utc == datetime(2026, 11, 2, 15, 0, tzinfo=UTC)


def test_departure_beyond_the_forecast_horizon_is_rejected():
    with pytest.raises(TripValidationError, match="forecast"):
        run(request(departure=NOW + timedelta(days=20)))


def test_departure_long_in_the_past_is_rejected():
    with pytest.raises(TripValidationError, match="past"):
        run(request(departure=NOW - timedelta(days=3)))


def test_same_origin_and_destination_is_rejected():
    with pytest.raises(TripValidationError, match="same"):
        run(request(destination=ORIGIN))


def test_failed_alternatives_are_skipped_with_a_warning():
    analysis = run(routing=FakeRouting(fail_via=True))

    assert [r.route_id for r in analysis.routes] == ["r1"]
    assert any("alternative" in w.lower() for w in analysis.warnings)


def test_failure_of_the_main_route_is_reported_not_hidden():
    with pytest.raises(ProviderError):
        run(routing=FakeRouting(fail_base=True))


def test_checkpoints_beyond_the_forecast_are_unknown_and_flagged():
    analysis = run(weather=FakeWeather(limit_hours=3))  # forecast ends 02:00 on the 2nd

    summary = analysis.routes[0].summary
    assert summary.unknown_miles == pytest.approx(200, abs=1)
    assert any("weather" in w.lower() and "unavailable" in w.lower() for w in analysis.warnings)


def test_weather_is_fetched_once_for_unique_grid_cells():
    weather = FakeWeather()

    run(weather=weather)

    assert len(weather.calls) == 1
    points = weather.calls[0][0]
    assert len(points) == len(set(points))
    assert all(round(lat, 1) == lat and round(lon, 1) == lon for lat, lon in points)


def test_heavy_load_turns_breezy_weather_severe():
    breezy = FakeWeather(lambda lat, lon, when: (40.0, 0.0, 0.0))

    light = run(request(load_lb=20_000), weather=breezy).routes[0].summary
    heavy = run(request(load_lb=50_000), weather=breezy).routes[0].summary

    assert light.severe_miles == 0 and light.high_miles > 0
    assert heavy.severe_miles > 0 and heavy.high_miles == 0


def test_blocked_everywhere_warns_that_no_route_is_travelable():
    gale = FakeWeather(lambda lat, lon, when: (60.0, 0.0, 0.0))

    analysis = run(weather=gale)

    assert analysis.recommendation.all_blocked is True
    assert any("No Travel" in w for w in analysis.warnings)


def test_alternatives_are_requested_through_offset_via_points_around_the_base_route():
    routing = FakeRouting()

    run(routing=routing)

    base_call, *via_calls = routing.calls
    assert base_call == (ORIGIN, DESTINATION)
    assert via_calls and all(len(call) == 3 and call[0] == ORIGIN for call in via_calls)
    assert {round(call[1][0] / DEG) for call in via_calls} >= {24, -24}  # left and right of route


def test_forecast_request_is_clamped_to_the_forecast_horizon():
    from datetime import date

    departure = NOW + timedelta(days=14, hours=20)  # 2026-11-16 08:00Z, last forecast day
    slow = FakeRouting(speed_mph=10)  # a 20 hour trip runs past the end of the forecast
    weather = FakeWeather()

    analysis = run(request(departure=departure), routing=slow, weather=weather)

    assert weather.calls[0][2] <= date(2026, 11, 16)
    assert analysis.routes[0].summary.unknown_miles > 0
    assert any("unavailable" in w.lower() for w in analysis.warnings)


def test_failed_alternative_lookups_are_reported_apart_from_geography_limits():
    routing = FakeRouting(via_error=ProviderError("Routing service is busy, please try again"))

    analysis = run(routing=routing)

    assert [r.route_id for r in analysis.routes] == ["r1"]
    assert any("failed" in w.lower() for w in analysis.warnings)


def test_unroutable_alternatives_are_not_reported_as_failures():
    analysis = run(routing=FakeRouting(fail_via=True))

    assert not any("failed" in w.lower() for w in analysis.warnings)


def test_trips_beyond_the_distance_limit_are_rejected_before_any_weather_is_fetched():
    weather = FakeWeather()

    with pytest.raises(TripValidationError, match="longer than"):
        run(request(destination=(0.0, 5000 * DEG)), weather=weather)

    assert weather.calls == []


def test_departure_that_overflows_the_calendar_is_a_validation_error():
    from datetime import timezone

    extreme = datetime(1, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=14)))

    with pytest.raises(TripValidationError, match="departure"):
        run(request(departure=extreme))


def test_unknown_timezone_name_falls_back_to_utc():
    analysis = run(
        request(departure=datetime(2026, 11, 2, 8, 0)), weather=FakeWeather(timezone="Mars/Olympus")
    )

    assert analysis.timezone == "UTC"
    assert analysis.departure_utc == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
