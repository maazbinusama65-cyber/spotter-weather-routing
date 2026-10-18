"""Per-checkpoint risk: worst of wind, rain and snow, then raised by the load rules."""

import math
from dataclasses import dataclass

from .levels import RiskLevel
from .thresholds import LOAD_RULES, RAIN_BANDS, SNOW_BANDS, WIND_BANDS, Band

__all__ = ["CheckpointRisk", "RiskLevel", "WeatherSample", "classify_checkpoint", "level_for"]


@dataclass(frozen=True)
class WeatherSample:
    """Weather at one checkpoint, already normalized to mph and inches per hour."""

    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float

    def __post_init__(self) -> None:
        for name in ("wind_mph", "rain_in_hr", "snow_in_hr"):
            value = getattr(self, name)
            if math.isnan(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative number, got {value!r}")


@dataclass(frozen=True)
class CheckpointRisk:
    level: RiskLevel
    wind_level: RiskLevel
    rain_level: RiskLevel
    snow_level: RiskLevel
    driver: str | None  # factor that set the level, None when everything is Low
    load_escalated: bool
    reason: str


def level_for(value: float, bands: tuple[Band, ...]) -> RiskLevel:
    for band in reversed(bands):
        if band.matches(value):
            return band.level
    return RiskLevel.LOW


def classify_checkpoint(sample: WeatherSample, load_lb: float) -> CheckpointRisk:
    if math.isnan(load_lb) or load_lb < 0:
        raise ValueError(f"load_lb must be a non-negative number, got {load_lb!r}")

    factor_levels = {
        "wind": level_for(sample.wind_mph, WIND_BANDS),
        "rain": level_for(sample.rain_in_hr, RAIN_BANDS),
        "snow": level_for(sample.snow_in_hr, SNOW_BANDS),
    }
    base_level = max(factor_levels.values())
    driver = next((name for name, lvl in factor_levels.items() if lvl == base_level), None)

    floors = [r.floor for r in LOAD_RULES if r.applies(sample.wind_mph, load_lb)]
    level = max([base_level, *floors])
    load_escalated = level > base_level
    if load_escalated:
        driver = "wind"

    return CheckpointRisk(
        level=level,
        wind_level=factor_levels["wind"],
        rain_level=factor_levels["rain"],
        snow_level=factor_levels["snow"],
        driver=driver if level > RiskLevel.LOW else None,
        load_escalated=load_escalated,
        reason=_reason(sample, load_lb, level, driver, load_escalated),
    )


def _reason(
    sample: WeatherSample,
    load_lb: float,
    level: RiskLevel,
    driver: str | None,
    load_escalated: bool,
) -> str:
    if level == RiskLevel.LOW or driver is None:
        return "Conditions are low risk"
    if load_escalated:
        return (
            f"{level.label}: wind {sample.wind_mph:g} mph is risky for a "
            f"{load_lb:,.0f} lb load"
        )
    readings = {
        "wind": f"wind {sample.wind_mph:g} mph",
        "rain": f"rain {sample.rain_in_hr:g} in/hr",
        "snow": f"snow {sample.snow_in_hr:g} in/hr",
    }
    return f"{level.label}: {readings[driver]}"
