"""Risk thresholds and load rules as data, straight from the assessment table.

Boundary rule: a band's lower bound is inclusive, except where the spec says
"greater than" (rain > 1.00 and snow > 3.0 are No Travel), marked ``strict``.
Bump RULESET_VERSION whenever any value below changes.
"""

from dataclasses import dataclass

from .levels import RiskLevel

RULESET_VERSION = "2026-10-1"


@dataclass(frozen=True)
class Band:
    """Applies when value >= lower (or value > lower if strict)."""

    lower: float
    level: RiskLevel
    strict: bool = False

    def matches(self, value: float) -> bool:
        return value > self.lower if self.strict else value >= self.lower


# Bands are listed from least to most severe; below the first band is LOW.
WIND_BANDS = (  # mph
    Band(25, RiskLevel.MODERATE),
    Band(35, RiskLevel.HIGH),
    Band(45, RiskLevel.SEVERE),
    Band(55, RiskLevel.NO_TRAVEL),
)
RAIN_BANDS = (  # inches per hour
    Band(0.10, RiskLevel.MODERATE),
    Band(0.25, RiskLevel.HIGH),
    Band(0.50, RiskLevel.SEVERE),
    Band(1.00, RiskLevel.NO_TRAVEL, strict=True),
)
SNOW_BANDS = (  # inches per hour
    Band(0.5, RiskLevel.MODERATE),
    Band(1.0, RiskLevel.HIGH),
    Band(2.0, RiskLevel.SEVERE),
    Band(3.0, RiskLevel.NO_TRAVEL, strict=True),
)


@dataclass(frozen=True)
class WindLoadRule:
    """Raises the checkpoint to at least ``floor`` for wind in [wind_min, wind_max)
    when the load is strictly heavier than ``load_gt`` lb."""

    wind_min: float
    wind_max: float
    load_gt: float
    floor: RiskLevel

    def applies(self, wind_mph: float, load_lb: float) -> bool:
        return self.wind_min <= wind_mph < self.wind_max and load_lb > self.load_gt


# Wind >= 55 mph is No Travel for any load; that is already the top wind band.
LOAD_RULES = (
    WindLoadRule(wind_min=45, wind_max=55, load_gt=30_000, floor=RiskLevel.NO_TRAVEL),
    WindLoadRule(wind_min=35, wind_max=45, load_gt=40_000, floor=RiskLevel.SEVERE),
)
