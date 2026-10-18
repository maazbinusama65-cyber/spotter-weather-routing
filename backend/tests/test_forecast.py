"""Looking up the forecast hour that matches a checkpoint's ETA."""

from datetime import UTC, datetime, timedelta

import pytest

from engine.forecast import HourlyForecast, sample_at
from engine.geo import MILES_PER_DEGREE_EQUATOR, simplify_polyline
from engine.risk import WeatherSample

START = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)


def forecast(hours=24, wind=None, rain=None, snow=None) -> HourlyForecast:
    return HourlyForecast(
        times=tuple(START + timedelta(hours=h) for h in range(hours)),
        wind_mph=tuple(wind if wind is not None else [float(h) for h in range(hours)]),
        rain_in_hr=tuple(rain if rain is not None else [0.0] * hours),
        snow_in_hr=tuple(snow if snow is not None else [0.0] * hours),
    )


def test_exact_hour_returns_that_hours_weather():
    result = sample_at(forecast(), START + timedelta(hours=5))

    assert result == WeatherSample(wind_mph=5.0, rain_in_hr=0.0, snow_in_hr=0.0)


@pytest.mark.parametrize(
    ("minutes", "expected_hour"),
    [(10, 5), (29, 5), (31, 6), (50, 6)],
)
def test_eta_snaps_to_the_nearest_forecast_hour(minutes, expected_hour):
    result = sample_at(forecast(), START + timedelta(hours=5, minutes=minutes))

    assert result.wind_mph == expected_hour


def test_all_three_factors_come_from_the_same_hour():
    data = forecast(wind=[1.0, 40.0, 3.0] + [0.0] * 21, rain=[0.0, 0.3, 0.0] + [0.0] * 21)

    result = sample_at(data, START + timedelta(hours=1))

    assert result == WeatherSample(wind_mph=40.0, rain_in_hr=0.3, snow_in_hr=0.0)


def test_eta_outside_the_forecast_range_has_no_weather():
    data = forecast(hours=24)

    assert sample_at(data, START - timedelta(hours=3)) is None
    assert sample_at(data, START + timedelta(hours=30)) is None


def test_eta_just_past_the_last_hour_still_uses_it():
    data = forecast(hours=24)

    assert sample_at(data, START + timedelta(hours=23, minutes=20)).wind_mph == 23


def test_missing_values_in_the_matched_hour_mean_unknown():
    data = forecast(wind=[None] + [1.0] * 23)

    assert sample_at(data, START) is None


def test_arrays_must_be_the_same_length():
    with pytest.raises(ValueError, match="length"):
        HourlyForecast(times=(START,), wind_mph=(1.0, 2.0), rain_in_hr=(0.0,), snow_in_hr=(0.0,))


def test_naive_eta_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        sample_at(forecast(), datetime(2026, 11, 2, 5))


def test_simplify_drops_points_on_a_straight_line_and_keeps_corners():
    deg = 1 / MILES_PER_DEGREE_EQUATOR
    line = tuple((0.0, i * deg) for i in range(0, 101))  # 100 collinear points
    corner = (*line, (50 * deg, 100 * deg))  # then turn north

    simplified = simplify_polyline(corner, tolerance_degrees=0.0005)

    assert simplified[0] == corner[0]
    assert simplified[-1] == corner[-1]
    assert (0.0, 100 * deg) in simplified  # the corner survives
    assert len(simplified) == 3


def test_simplify_keeps_points_that_deviate_more_than_the_tolerance():
    coords = ((0.0, 0.0), (0.01, 0.5), (0.0, 1.0))

    assert simplify_polyline(coords, tolerance_degrees=0.001) == coords
    assert simplify_polyline(coords, tolerance_degrees=0.1) == (coords[0], coords[-1])


def test_simplify_leaves_two_points_alone():
    coords = ((0.0, 0.0), (1.0, 1.0))

    assert simplify_polyline(coords, tolerance_degrees=1) == coords
