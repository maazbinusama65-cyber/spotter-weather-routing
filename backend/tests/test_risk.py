"""Risk classification: per-factor bands, worst-factor combination, and load escalation.

Boundary rule (documented in the README): a band's lower bound is inclusive, except
where the spec says strictly greater (rain > 1.00 and snow > 3.0 are No Travel).
"""

import pytest

from engine.risk import RiskLevel, WeatherSample, classify_checkpoint, level_for
from engine.thresholds import RAIN_BANDS, SNOW_BANDS, WIND_BANDS

LOW, MOD, HIGH, SEV, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)

LIGHT_LOAD = 10_000


@pytest.mark.parametrize(
    ("wind", "expected"),
    [
        (0, LOW),
        (24.99, LOW),
        (25, MOD),
        (34.99, MOD),
        (35, HIGH),
        (44.99, HIGH),
        (45, SEV),
        (54.99, SEV),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_bands(wind, expected):
    assert level_for(wind, WIND_BANDS) == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0, LOW),
        (0.099, LOW),
        (0.10, MOD),
        (0.249, MOD),
        (0.25, HIGH),
        (0.499, HIGH),
        (0.50, SEV),
        (1.00, SEV),  # NO_TRAVEL is strictly > 1.00
        (1.001, NT),
        (3.0, NT),
    ],
)
def test_rain_bands(rain, expected):
    assert level_for(rain, RAIN_BANDS) == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0, LOW),
        (0.499, LOW),
        (0.5, MOD),
        (0.999, MOD),
        (1.0, HIGH),
        (1.999, HIGH),
        (2.0, SEV),
        (3.0, SEV),  # NO_TRAVEL is strictly > 3.0
        (3.001, NT),
    ],
)
def test_snow_bands(snow, expected):
    assert level_for(snow, SNOW_BANDS) == expected


def test_checkpoint_level_is_worst_of_all_factors():
    sample = WeatherSample(wind_mph=10, rain_in_hr=0.3, snow_in_hr=2.5)

    result = classify_checkpoint(sample, LIGHT_LOAD)

    assert result.level == SEV
    assert result.driver == "snow"
    assert (result.wind_level, result.rain_level, result.snow_level) == (LOW, HIGH, SEV)


def test_calm_weather_is_low_with_no_driver():
    result = classify_checkpoint(WeatherSample(5, 0, 0), LIGHT_LOAD)

    assert result.level == LOW
    assert result.driver is None


@pytest.mark.parametrize("load", [0, LIGHT_LOAD, 80_000])
def test_wind_55_is_no_travel_for_any_load(load):
    result = classify_checkpoint(WeatherSample(55, 0, 0), load)

    assert result.level == NT


@pytest.mark.parametrize(
    ("load", "expected"),
    [
        (30_000, SEV),  # not strictly over 30,000 lb
        (30_001, NT),
        (45_000, NT),
    ],
)
def test_wind_45_to_54_with_heavy_load_is_no_travel(load, expected):
    result = classify_checkpoint(WeatherSample(50, 0, 0), load)

    assert result.level == expected


@pytest.mark.parametrize(
    ("load", "expected"),
    [
        (40_000, HIGH),  # not strictly over 40,000 lb
        (40_001, SEV),
        (79_999, SEV),
    ],
)
def test_wind_35_to_44_with_heavy_load_is_severe(load, expected):
    result = classify_checkpoint(WeatherSample(40, 0, 0), load)

    assert result.level == expected


def test_load_rule_boundaries_apply_at_wind_band_edges():
    assert classify_checkpoint(WeatherSample(45, 0, 0), 30_001).level == NT
    assert classify_checkpoint(WeatherSample(44.99, 0, 0), 30_001).level == HIGH
    assert classify_checkpoint(WeatherSample(44.99, 0, 0), 40_001).level == SEV
    assert classify_checkpoint(WeatherSample(35, 0, 0), 40_001).level == SEV
    assert classify_checkpoint(WeatherSample(34.99, 0, 0), 80_000).level == MOD


def test_load_escalation_is_reported_for_the_ui():
    escalated = classify_checkpoint(WeatherSample(40, 0, 0), 50_000)
    plain = classify_checkpoint(WeatherSample(40, 0, 0), 10_000)

    assert escalated.load_escalated is True
    assert "load" in escalated.reason.lower()
    assert plain.load_escalated is False


def test_load_never_lowers_risk():
    sample = WeatherSample(wind_mph=20, rain_in_hr=0.6, snow_in_hr=0)

    result = classify_checkpoint(sample, 80_000)

    assert result.level == SEV  # driven by rain; wind load rules do not apply


@pytest.mark.parametrize("wind", [x / 2 for x in range(0, 140)])
def test_risk_is_monotonic_in_load(wind):
    sample = WeatherSample(wind_mph=wind, rain_in_hr=0, snow_in_hr=0)
    levels = [classify_checkpoint(sample, load).level for load in (0, 30_000, 30_001, 40_001)]

    assert levels == sorted(levels)


@pytest.mark.parametrize("bad", [-1, float("nan")])
def test_invalid_weather_values_are_rejected(bad):
    with pytest.raises(ValueError):
        classify_checkpoint(WeatherSample(bad, 0, 0), LIGHT_LOAD)


def test_negative_load_is_rejected():
    with pytest.raises(ValueError):
        classify_checkpoint(WeatherSample(10, 0, 0), -1)
