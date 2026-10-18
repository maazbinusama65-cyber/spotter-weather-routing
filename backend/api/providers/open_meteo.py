"""Open-Meteo adapter: hourly wind, rain and snow forecasts, normalized to mph and in/hr."""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import httpx

from engine.forecast import HourlyForecast
from engine.geo import LatLon

from .types import ProviderError

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MAX_POINTS_PER_REQUEST = 50
MAX_PARALLEL_REQUESTS = 4
HOURLY_VARIABLES = "wind_speed_10m,rain,showers,snowfall"
_TIME_FORMAT = "%Y-%m-%dT%H:%M"


class OpenMeteoClient:
    def __init__(
        self, timeout: float = 10.0, http: httpx.Client | None = None, url: str = FORECAST_URL
    ) -> None:
        self._http = http or httpx.Client(timeout=timeout)
        self._url = url

    def forecasts(self, points: Sequence[LatLon], start: date, end: date) -> list[HourlyForecast]:
        batches = [
            points[first : first + MAX_POINTS_PER_REQUEST]
            for first in range(0, len(points), MAX_POINTS_PER_REQUEST)
        ]
        if not batches:
            return []
        workers = min(len(batches), MAX_PARALLEL_REQUESTS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = pool.map(lambda batch: self._fetch_batch(batch, start, end), batches)
            return [forecast for batch in fetched for forecast in batch]

    def _fetch_batch(self, batch: Sequence[LatLon], start: date, end: date) -> list[HourlyForecast]:
        data = self._get(
            {
                **_coordinate_params(batch),
                "hourly": HOURLY_VARIABLES,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
        )
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(batch):
            raise ProviderError("Weather service returned an unexpected response")
        try:
            return [_parse_location(location) for location in locations]
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("Weather service returned an unexpected response") from error

    def timezone_name(self, point: LatLon) -> str:
        data = self._get(
            {
                **_coordinate_params([point]),
                "hourly": "temperature_2m",
                "forecast_days": 1,
                "timezone": "auto",
            }
        )
        try:
            return str(data["timezone"])
        except (KeyError, TypeError) as error:
            raise ProviderError("Weather service returned an unexpected response") from error

    def _get(self, params: dict):
        try:
            response = self._http.get(self._url, params=params)
        except httpx.TimeoutException as error:
            raise ProviderError("Weather service timed out") from error
        except httpx.HTTPError as error:
            raise ProviderError("Weather service is unreachable") from error
        if response.status_code == 429:
            raise ProviderError("Weather service is busy, please try again shortly")
        if response.status_code >= 400:
            raise ProviderError("Weather service is unavailable")
        try:
            return response.json()
        except ValueError as error:
            raise ProviderError("Weather service returned an unexpected response") from error


def _coordinate_params(points: Sequence[LatLon]) -> dict[str, str]:
    return {
        "latitude": ",".join(repr(round(lat, 4)) for lat, _ in points),
        "longitude": ",".join(repr(round(lon, 4)) for _, lon in points),
    }


def _parse_location(location: dict) -> HourlyForecast:
    hourly = location["hourly"]
    times = tuple(
        datetime.strptime(stamp, _TIME_FORMAT).replace(tzinfo=UTC) for stamp in hourly["time"]
    )
    rain = [
        None if r is None else r + (s or 0.0)
        for r, s in zip(hourly["rain"], hourly["showers"], strict=True)
    ]
    return HourlyForecast(
        times=times,
        wind_mph=tuple(hourly["wind_speed_10m"]),  # instantaneous at the timestamp
        rain_in_hr=_hour_starting_at(rain),
        snow_in_hr=_hour_starting_at(hourly["snowfall"]),
    )


def _hour_starting_at(preceding_hour_totals: list) -> tuple:
    """Open-Meteo reports precipitation at HH:00 as the total for the hour *ending* then.
    Shift it so each value describes the hour starting at its timestamp, matching how a
    truck passing a checkpoint at HH:xx experiences it. The last hour has no value."""
    return (*preceding_hour_totals[1:], None)
