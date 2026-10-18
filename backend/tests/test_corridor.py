"""Sampling the trip corridor for the heatmap, and turning a forecast into hourly levels."""

from datetime import UTC, datetime, timedelta

import pytest

from engine.corridor import corridor_points
from engine.forecast import HourlyForecast
from engine.geo import MILES_PER_DEGREE_EQUATOR
from engine.heat import hourly_levels
from engine.sampling import RouteGeometry

DEG = 1 / MILES_PER_DEGREE_EQUATOR
START = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)


def eastbound(miles: float, lat: float = 0.0) -> RouteGeometry:
    return RouteGeometry(coordinates=((lat, 0.0), (lat, miles * DEG)), duration_s=3600)


def test_points_are_spaced_along_the_route_including_both_ends():
    points = corridor_points([eastbound(100)], min_spacing_miles=25)

    assert len(points) == 5
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (0.0, round(100 * DEG, 1))


def test_points_are_snapped_to_weather_grid_cells():
    points = corridor_points([eastbound(137)], min_spacing_miles=25)

    assert all(round(lat, 1) == lat and round(lon, 1) == lon for lat, lon in points)


def test_spacing_widens_on_long_routes_to_bound_the_point_count():
    short = corridor_points([eastbound(500)], min_spacing_miles=25, target_per_route=20)
    long = corridor_points([eastbound(3000)], min_spacing_miles=25, target_per_route=20)

    assert len(short) <= 22
    assert len(long) <= 22  # 3000 miles still sampled with about 20 points


def test_shared_stretches_of_several_routes_are_not_duplicated():
    one = corridor_points([eastbound(200)], min_spacing_miles=25)
    two = corridor_points([eastbound(200), eastbound(200)], min_spacing_miles=25)

    assert two == one


def test_alternatives_add_their_own_points_to_widen_the_corridor():
    base = corridor_points([eastbound(200)], min_spacing_miles=25)
    both = corridor_points([eastbound(200), eastbound(200, lat=0.5)], min_spacing_miles=25)

    assert len(both) == 2 * len(base)
    assert {lat for lat, _ in both} == {0.0, 0.5}


def test_point_count_is_capped_evenly_and_deterministically():
    routes = [eastbound(400, lat=i * 0.3) for i in range(8)]

    first = corridor_points(routes, min_spacing_miles=10, max_points=40)
    second = corridor_points(routes, min_spacing_miles=10, max_points=40)

    assert len(first) <= 40
    assert first == second
    assert {lat for lat, _ in first} >= {0.0, 2.1}  # thinned, not truncated to one route


def test_no_routes_means_no_points():
    assert corridor_points([], min_spacing_miles=25) == []


def forecast(wind, hours=None, rain=None, snow=None) -> HourlyForecast:
    n = hours if hours is not None else len(wind)
    return HourlyForecast(
        times=tuple(START + timedelta(hours=h) for h in range(n)),
        wind_mph=tuple(wind),
        rain_in_hr=tuple(rain if rain is not None else [0.0] * n),
        snow_in_hr=tuple(snow if snow is not None else [0.0] * n),
    )


def test_calm_weather_is_level_zero_every_hour():
    assert hourly_levels(forecast([5.0] * 4), START, 4, load_lb=20_000) == "0000"


def test_levels_follow_the_risk_rules_hour_by_hour():
    data = forecast([5.0, 30.0, 40.0, 50.0, 60.0])

    assert hourly_levels(data, START, 5, load_lb=10_000) == "01234"


def test_the_same_wind_is_riskier_for_a_heavier_load():
    data = forecast([5.0, 5.0, 40.0, 5.0])

    assert hourly_levels(data, START, 4, load_lb=20_000) == "0020"
    assert hourly_levels(data, START, 4, load_lb=50_000) == "0030"


def test_rain_and_snow_count_too():
    data = forecast([5.0] * 3, rain=[0.0, 0.3, 0.0], snow=[0.0, 0.0, 2.5])

    assert hourly_levels(data, START, 3, load_lb=10_000) == "023"


def test_series_starts_at_the_requested_hour():
    data = forecast([5.0, 5.0, 40.0, 5.0])

    assert hourly_levels(data, START + timedelta(hours=2), 2, load_lb=20_000) == "20"


def test_hours_beyond_the_forecast_are_marked_unknown():
    data = forecast([5.0, 5.0, 5.0])

    assert hourly_levels(data, START, 6, load_lb=10_000) == "000---"


def test_missing_values_are_marked_unknown():
    data = forecast([5.0, None, 5.0])

    assert hourly_levels(data, START, 3, load_lb=10_000) == "0-0"


def test_zero_hours_is_an_empty_series():
    assert hourly_levels(forecast([5.0]), START, 0, load_lb=10_000) == ""


@pytest.mark.parametrize("bad", [-1])
def test_negative_hours_are_rejected(bad):
    with pytest.raises(ValueError, match="hours"):
        hourly_levels(forecast([5.0]), START, bad, load_lb=10_000)
