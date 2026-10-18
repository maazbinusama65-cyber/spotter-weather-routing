"""OpenRouteService adapter: request shape, response parsing, and error handling."""

import json
from pathlib import Path

import httpx
import pytest

from api.providers.ors import OrsClient
from api.providers.types import ProviderError, RouteNotFound

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "ors_directions.json").read_text()
)
API_KEY = "test-key-123"
WAYPOINTS = [(39.74, -104.99), (39.80, -104.20)]


def client_for(handler) -> OrsClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OrsClient(api_key=API_KEY, timeout=5, http=http)


def json_response(payload, status=200):
    return httpx.Response(status, json=payload)


def test_route_posts_lon_lat_waypoints_to_the_hgv_profile_with_key_in_header():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return json_response(FIXTURE)

    client_for(handler).route(WAYPOINTS)

    assert seen["url"].endswith("/v2/directions/driving-hgv/geojson")
    assert API_KEY not in seen["url"]
    assert seen["auth"] == API_KEY
    assert seen["body"]["coordinates"] == [[-104.99, 39.74], [-104.2, 39.8]]
    assert seen["body"]["instructions"] is True


def test_route_parses_geometry_as_lat_lon_and_total_duration():
    option = client_for(lambda r: json_response(FIXTURE)).route(WAYPOINTS)

    assert option.geometry.coordinates[0] == (39.74, -104.99)
    assert option.geometry.coordinates[-1] == (39.8, -104.2)
    assert len(option.geometry.coordinates) == 5
    assert option.geometry.duration_s == 1300


def test_route_builds_per_vertex_durations_from_steps():
    option = client_for(lambda r: json_response(FIXTURE)).route(WAYPOINTS)

    profile = option.geometry.cumulative_duration_s
    assert profile is not None
    assert len(profile) == 5
    assert profile[0] == 0
    assert profile[2] == pytest.approx(600)  # end of first step
    assert profile[3] == pytest.approx(900)
    assert profile[4] == pytest.approx(1300)
    assert 250 < profile[1] < 350  # inside the first step, proportional to distance
    assert list(profile) == sorted(profile)


def test_route_summarises_main_roads_by_distance_and_skips_unnamed_steps():
    option = client_for(lambda r: json_response(FIXTURE)).route(WAYPOINTS)

    assert option.via == "I 70, I 76"


def test_route_without_steps_still_works_with_constant_speed():
    payload = json.loads(json.dumps(FIXTURE))
    payload["features"][0]["properties"]["segments"] = []

    option = client_for(lambda r: json_response(payload)).route(WAYPOINTS)

    assert option.geometry.cumulative_duration_s is None
    assert option.via == ""


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_is_reported_generically_to_users_and_in_detail_to_the_log(status, caplog):
    client = client_for(lambda r: json_response({"error": "nope"}, status))

    with pytest.raises(ProviderError, match="unavailable") as info:
        client.route(WAYPOINTS)

    assert "key" not in str(info.value).lower()
    assert "rejected the API key" in caplog.text


def test_rate_limit_is_reported_as_busy():
    client = client_for(lambda r: json_response({"error": "limit"}, 429))

    with pytest.raises(ProviderError, match="busy"):
        client.route(WAYPOINTS)


@pytest.mark.parametrize("status", [400, 404])
def test_unroutable_points_raise_route_not_found(status):
    body = {"error": {"code": 2010, "message": "Could not find routable point"}}
    client = client_for(lambda r: json_response(body, status))

    with pytest.raises(RouteNotFound):
        client.route(WAYPOINTS)


def test_other_bad_requests_are_provider_errors_not_route_not_found(caplog):
    body = {"error": {"code": 2004, "message": "Request parameters exceed the server limits"}}
    client = client_for(lambda r: json_response(body, 400))

    with pytest.raises(ProviderError) as info:
        client.route(WAYPOINTS)

    assert not isinstance(info.value, RouteNotFound)
    assert "2004" in caplog.text


def test_server_error_is_a_provider_error_but_not_route_not_found():
    client = client_for(lambda r: json_response({}, 503))

    with pytest.raises(ProviderError) as info:
        client.route(WAYPOINTS)
    assert not isinstance(info.value, RouteNotFound)


def test_timeout_is_a_provider_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError, match="timed out"):
        client_for(handler).route(WAYPOINTS)


def test_malformed_response_is_a_provider_error():
    client = client_for(lambda r: json_response({"features": []}))

    with pytest.raises(ProviderError, match="unexpected"):
        client.route(WAYPOINTS)


def test_missing_api_key_fails_fast_without_calling_the_network():
    def handler(request):
        raise AssertionError("no request should be made")

    client = OrsClient(
        api_key="", timeout=5, http=httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(ProviderError, match="not configured") as info:
        client.route(WAYPOINTS)

    assert "ORS_API_KEY" not in str(info.value)


GEOCODE_RESPONSE = {
    "features": [
        {
            "geometry": {"type": "Point", "coordinates": [-104.9847, 39.7392]},
            "properties": {"label": "Denver, CO, USA"},
        },
        {
            "geometry": {"type": "Point", "coordinates": [-87.6298, 41.8781]},
            "properties": {"label": "Chicago, IL, USA"},
        },
    ]
}


def test_geocode_returns_places_with_lat_lon():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = request.url
        seen["auth"] = request.headers.get("Authorization")
        return json_response(GEOCODE_RESPONSE)

    places = client_for(handler).geocode("Denver")

    assert [p.label for p in places] == ["Denver, CO, USA", "Chicago, IL, USA"]
    assert (places[0].lat, places[0].lon) == (39.7392, -104.9847)
    assert seen["url"].path.endswith("/geocode/search")
    assert seen["url"].params["text"] == "Denver"
    assert seen["auth"] == API_KEY
    assert API_KEY not in str(seen["url"])


def test_geocode_with_no_matches_returns_empty_list():
    assert client_for(lambda r: json_response({"features": []})).geocode("zzzz") == []


def test_geocode_skips_features_without_usable_coordinates():
    payload = {"features": [{"geometry": None, "properties": {"label": "bad"}}]}

    assert client_for(lambda r: json_response(payload)).geocode("x") == []


LIVE_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "ors_directions_live.json").read_text()
)


def test_real_ors_response_parses_with_a_complete_duration_profile():
    """A genuine driving-hgv response (Denver to Fort Collins) recorded from the live API."""
    option = client_for(lambda r: json_response(LIVE_FIXTURE)).route(
        [(39.7392, -104.9847), (40.5853, -105.0844)]
    )

    geometry = option.geometry
    profile = geometry.cumulative_duration_s
    assert len(geometry.coordinates) == 563
    assert profile is not None and len(profile) == 563
    assert profile[0] == 0
    assert profile[-1] == pytest.approx(geometry.duration_s, rel=0.01)
    assert list(profile) == sorted(profile)
    assert option.via
