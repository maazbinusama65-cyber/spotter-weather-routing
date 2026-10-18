"""Per-hour risk series for one location, used by the heatmap forecast slider."""

from datetime import datetime, timedelta

from .forecast import HourlyForecast, sample_at
from .risk import classify_checkpoint

UNKNOWN_LEVEL = "-"


def hourly_levels(forecast: HourlyForecast, start: datetime, hours: int, load_lb: float) -> str:
    """One character per hour from ``start``: the risk level 0-4, or ``-`` when the forecast
    has no usable value for that hour. A string keeps 49 hours of one point to 49 bytes."""
    if hours < 0:
        raise ValueError("hours must not be negative")
    levels = []
    for hour in range(hours):
        sample = sample_at(forecast, start + timedelta(hours=hour))
        if sample is None:
            levels.append(UNKNOWN_LEVEL)
        else:
            levels.append(str(int(classify_checkpoint(sample, load_lb).level)))
    return "".join(levels)
