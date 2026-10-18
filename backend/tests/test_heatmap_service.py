"""Heatmap service: corridor grid with a 0-48 hour risk series per point."""

from datetime import UTC, datetime, timedelta

import pytest

from api.providers.types import ProviderError
from api.services.heatmap import HEATMAP_HOURS, build_heatmap
from api.services.trip import TripRequest, TripValidationError
from engine.geo import MILES_PER_DEGREE_EQUATOR
from tests.fakes import FakeRouting, FakeWeather

DEG = 1 / MILES_PER_DEGREE_EQUATOR
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
DEPARTURE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
ORIGIN = (0.0, 0.0)
DESTINATION = (0.0, 300 * DEG)


def request(**overrides) -> TripRequest:
    fields = dict(
        origin=ORIGIN,
        destination=DESTINATION,
        departure=DEPARTURE,
        load_lb=20_000,
        interval_miles=25,
    )
    return TripRequest(**{**fields, **overrides})


def run(req=None, routing=None, weather=None):
    return build_heatmap(req or request(), routing or FakeRouting(), weather or FakeWeather(), NOW)


def test_every_point_carries_one_level_per_hour():
    heatmap = run()

    assert HEATMAP_HOURS == 49
    assert heatmap.hours == 49
    assert len(heatmap.points) > 10
    assert all(len(point.levels) == 49 for point in heatmap.points)
    assert set("".join(p.levels for p in heatmap.points)) == {"0"}  # calm everywhere


def test_the_series_starts_at_the_departure_hour():
    heatmap = run(request(departure=datetime(2026, 11, 2, 8, 40, tzinfo=UTC)))

    assert heatmap.start == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)


def test_levels_change_with_the_forecast_hour_not_the_eta():
    def storm_after_ten(lat, lon, when):
        return (
            (48.0, 0.0, 0.0) if when >= datetime(2026, 11, 2, 10, tzinfo=UTC) else (5.0, 0.0, 0.0)
        )

    heatmap = run(weather=FakeWeather(storm_after_ten))

    for point in heatmap.points:
        assert point.levels[:2] == "00"
        assert set(point.levels[2:]) == {"3"}  # 10:00 is hour index 2


def test_load_changes_the_levels():
    breezy = FakeWeather(lambda lat, lon, when: (40.0, 0.0, 0.0))

    light = run(request(load_lb=20_000), weather=breezy)
    heavy = run(request(load_lb=50_000), weather=breezy)

    assert {c for p in light.points for c in p.levels} == {"2"}
    assert {c for p in heavy.points for c in p.levels} == {"3"}


def test_corridor_covers_the_alternatives_not_just_the_main_route():
    heatmap = run()

    assert any(abs(point.lat) > 0.1 for point in heatmap.points)


def test_weather_is_fetched_in_one_call_for_unique_cells():
    weather = FakeWeather()

    heatmap = run(weather=weather)

    assert len(weather.calls) == 1
    requested = weather.calls[0][0]
    assert len(requested) == len(set(requested)) == len(heatmap.points)


def test_point_count_is_bounded_to_protect_the_weather_quota():
    long_trip = request(destination=(0.0, 3000 * DEG))

    heatmap = run(long_trip)

    assert len(heatmap.points) <= 150


def test_forecast_shorter_than_the_window_is_marked_unknown_with_a_warning():
    heatmap = run(weather=FakeWeather(limit_hours=30))  # forecast ends 06:00 on the 3rd

    tail = {p.levels[-1] for p in heatmap.points}
    assert tail == {"-"}
    assert any("forecast" in w.lower() for w in heatmap.warnings)


def test_naive_departure_is_read_in_the_origin_timezone():
    weather = FakeWeather(timezone="America/Chicago")

    heatmap = run(request(departure=datetime(2026, 11, 2, 8, 0)), weather=weather)

    assert heatmap.timezone == "America/Chicago"
    assert heatmap.start == datetime(2026, 11, 2, 14, 0, tzinfo=UTC)


def test_forecast_request_never_goes_past_the_forecast_horizon():
    weather = FakeWeather()
    late = NOW + timedelta(days=14, hours=20)

    heatmap = run(request(departure=late), weather=weather)

    from datetime import date

    assert weather.calls[0][2] <= date(2026, 11, 16)
    assert all(p.levels.endswith("-") for p in heatmap.points)


def test_same_origin_and_destination_is_rejected():
    with pytest.raises(TripValidationError, match="same"):
        run(request(destination=ORIGIN))


def test_departure_in_the_far_future_is_rejected():
    with pytest.raises(TripValidationError, match="forecast"):
        run(request(departure=NOW + timedelta(days=20)))


def test_main_route_failure_is_reported():
    with pytest.raises(ProviderError):
        run(routing=FakeRouting(fail_base=True))


def test_without_alternatives_the_main_route_corridor_is_still_returned():
    heatmap = run(routing=FakeRouting(fail_via=True))

    assert len(heatmap.points) > 5
    assert all(abs(p.lat) < 0.1 for p in heatmap.points)
