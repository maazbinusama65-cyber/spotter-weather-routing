"""Open-Meteo adapter: request shape, response parsing, batching, and errors."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from api.providers.open_meteo import MAX_POINTS_PER_REQUEST, OpenMeteoClient
from api.providers.types import ProviderError

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "open_meteo_two_locations.json").read_text()
)
DAY = date(2026, 10, 20)


def client_for(handler) -> OpenMeteoClient:
    return OpenMeteoClient(timeout=5, http=httpx.Client(transport=httpx.MockTransport(handler)))


def location(hours, wind, rain, showers, snow, **extra):
    times = [f"2026-10-20T{h:02d}:00" for h in range(hours)]
    return {
        "hourly": {
            "time": times,
            "wind_speed_10m": wind,
            "rain": rain,
            "showers": showers,
            "snowfall": snow,
        },
        **extra,
    }


def test_request_asks_for_mph_inches_and_utc_with_comma_separated_points():
    seen = {}

    def handler(request: httpx.Request):
        seen["params"] = request.url.params
        return httpx.Response(200, json=FIXTURE)

    client_for(handler).forecasts([(39.74, -104.99), (41.88, -87.63)], DAY, DAY)

    params = seen["params"]
    assert params["latitude"] == "39.74,41.88"
    assert params["longitude"] == "-104.99,-87.63"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timezone"] == "UTC"
    assert (params["start_date"], params["end_date"]) == ("2026-10-20", "2026-10-20")
    assert {"wind_speed_10m", "rain", "showers", "snowfall"} <= set(params["hourly"].split(","))


def test_recorded_response_parses_into_one_forecast_per_point():
    forecasts = client_for(lambda r: httpx.Response(200, json=FIXTURE)).forecasts(
        [(39.74, -104.99), (41.88, -87.63)], DAY, DAY
    )

    assert len(forecasts) == 2
    assert forecasts[0].times[0] == datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
    assert len(forecasts[0].times) == 8
    assert forecasts[0].wind_mph[1] == FIXTURE[0]["hourly"]["wind_speed_10m"][1]


def test_rain_is_rain_plus_showers_for_the_hour_starting_at_each_timestamp():
    # Open-Meteo precipitation at HH:00 is the total for the hour *ending* at HH:00, so the
    # adapter shifts it to describe the hour starting at each timestamp.
    payload = [location(3, [10.0, 12.0, 14.0], [0.0, 0.1, 0.3], [0.0, 0.05, 0.2], [0.0] * 3)]

    forecast = client_for(lambda r: httpx.Response(200, json=payload)).forecasts(
        [(1.0, 1.0)], DAY, DAY
    )[0]

    assert forecast.rain_in_hr[:2] == pytest.approx((0.15, 0.5))
    assert forecast.rain_in_hr[2] is None  # no following hour to describe the last one
    assert forecast.wind_mph == (10.0, 12.0, 14.0)  # wind is instantaneous, not shifted


def test_snowfall_is_also_shifted_to_the_hour_starting_at_each_timestamp():
    payload = [location(3, [1.0] * 3, [0.0] * 3, [0.0] * 3, [0.0, 0.7, 2.5])]

    forecast = client_for(lambda r: httpx.Response(200, json=payload)).forecasts(
        [(1.0, 1.0)], DAY, DAY
    )[0]

    assert forecast.snow_in_hr == (0.7, 2.5, None)


def test_single_location_response_is_a_dict_not_a_list():
    payload = location(2, [10.0, 12.0], [0.0, 0.0], [0.0, 0.0], [0.5, 0.0])

    forecasts = client_for(lambda r: httpx.Response(200, json=payload)).forecasts(
        [(1.0, 1.0)], DAY, DAY
    )

    assert len(forecasts) == 1
    assert forecasts[0].wind_mph == (10.0, 12.0)


def test_null_values_stay_missing():
    payload = [location(3, [None, 12.0, 9.0], [0.0, None, 0.4], [0.0] * 3, [0.0] * 3)]

    forecast = client_for(lambda r: httpx.Response(200, json=payload)).forecasts(
        [(1.0, 1.0)], DAY, DAY
    )[0]

    assert forecast.wind_mph == (None, 12.0, 9.0)
    assert forecast.rain_in_hr == (None, 0.4, None)


def test_many_points_are_split_into_batches_and_order_is_preserved():
    requests = []

    def handler(request: httpx.Request):
        lats = request.url.params["latitude"].split(",")
        requests.append(len(lats))
        payload = [location(1, [float(lat)], [0.0], [0.0], [0.0]) for lat in lats]
        return httpx.Response(200, json=payload)

    points = [(float(i), 0.0) for i in range(MAX_POINTS_PER_REQUEST * 2 + 5)]

    forecasts = client_for(handler).forecasts(points, DAY, DAY)

    assert requests == [MAX_POINTS_PER_REQUEST, MAX_POINTS_PER_REQUEST, 5]
    assert [f.wind_mph[0] for f in forecasts] == [p[0] for p in points]


def test_no_points_makes_no_request():
    def handler(request):
        raise AssertionError("no request should be made")

    assert client_for(handler).forecasts([], DAY, DAY) == []


def test_response_with_wrong_number_of_locations_is_an_error():
    payload = [location(1, [1.0], [0.0], [0.0], [0.0])]

    with pytest.raises(ProviderError, match="unexpected"):
        client_for(lambda r: httpx.Response(200, json=payload)).forecasts(
            [(1.0, 1.0), (2.0, 2.0)], DAY, DAY
        )


@pytest.mark.parametrize(("status", "word"), [(429, "busy"), (500, "unavailable")])
def test_http_errors_become_provider_errors(status, word):
    client = client_for(lambda r: httpx.Response(status, json={"reason": "x"}))

    with pytest.raises(ProviderError, match=word):
        client.forecasts([(1.0, 1.0)], DAY, DAY)


def test_timeout_is_a_provider_error():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        client_for(handler).forecasts([(1.0, 1.0)], DAY, DAY)


def test_timezone_name_uses_auto_timezone_for_the_point():
    seen = {}

    def handler(request: httpx.Request):
        seen["params"] = request.url.params
        return httpx.Response(200, json={"timezone": "America/Denver"})

    assert client_for(handler).timezone_name((39.74, -104.99)) == "America/Denver"
    assert seen["params"]["timezone"] == "auto"
    assert seen["params"]["latitude"] == "39.74"
