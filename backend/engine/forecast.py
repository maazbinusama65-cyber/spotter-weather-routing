"""Hourly forecast for one location, and lookup of the hour matching a checkpoint's ETA."""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime

from .risk import WeatherSample

# An ETA further than this from the nearest forecast hour is treated as outside the forecast.
_MAX_GAP_SECONDS = 30 * 60


@dataclass(frozen=True)
class HourlyForecast:
    """Parallel hourly series in mph and inches per hour. ``None`` marks a missing value."""

    times: tuple[datetime, ...]  # timezone-aware, ascending
    wind_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]

    def __post_init__(self) -> None:
        sizes = {len(self.times), len(self.wind_mph), len(self.rain_in_hr), len(self.snow_in_hr)}
        if len(sizes) != 1:
            raise ValueError("forecast series must all have the same length")


def sample_at(forecast: HourlyForecast, eta: datetime) -> WeatherSample | None:
    """Weather for the forecast hour nearest ``eta``; None if outside the forecast or missing."""
    if eta.tzinfo is None:
        raise ValueError("eta must be timezone-aware")
    if not forecast.times:
        return None

    index = _nearest_index(forecast.times, eta)
    if abs((forecast.times[index] - eta).total_seconds()) > _MAX_GAP_SECONDS:
        return None

    wind, rain, snow = (
        forecast.wind_mph[index],
        forecast.rain_in_hr[index],
        forecast.snow_in_hr[index],
    )
    if wind is None or rain is None or snow is None:
        return None
    return WeatherSample(wind_mph=wind, rain_in_hr=rain, snow_in_hr=snow)


def _nearest_index(times: tuple[datetime, ...], eta: datetime) -> int:
    after = bisect_left(times, eta)
    if after == 0:
        return 0
    if after == len(times):
        return len(times) - 1
    before = after - 1
    return before if eta - times[before] <= times[after] - eta else after
