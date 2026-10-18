"""HTTP API: request validation, response shape, and error mapping."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from api.providers.types import ProviderError
from engine.geo import MILES_PER_DEGREE_EQUATOR
from tests.fakes import FakeRouting, FakeWeather

DEG = 1 / MILES_PER_DEGREE_EQUATOR


def soon() -> str:
    return (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")


@pytest.fixture
def providers(monkeypatch):
    routing, weather = FakeRouting(), FakeWeather()
    monkeypatch.setattr("api.views.get_providers", lambda: (routing, weather))
    return routing, weather


@pytest.fixture
def client():
    return APIClient()


def body(**overrides):
    payload = {
        "origin": {"lat": 0.0, "lon": 0.0, "label": "Start"},
        "destination": {"lat": 0.0, "lon": 200 * DEG, "label": "End"},
        "departure": soon(),
        "load_lb": 42_000,
        "interval_miles": 50,
    }
    return {**payload, **overrides}


def post(client, **overrides):
    return client.post("/api/analyze", body(**overrides), format="json")


def test_analyze_returns_routes_checkpoints_and_a_recommendation(client, providers):
    response = post(client)

    assert response.status_code == 200
    data = response.json()
    assert len(data["routes"]) == 3
    assert data["recommendation"]["route_id"] in {r["id"] for r in data["routes"]}
    assert data["recommendation"]["reason"]
    assert data["interval_miles"] == 50
    assert data["load_lb"] == 42_000
    assert data["timezone"] == "UTC"
    assert data["ruleset_version"]
    assert [lvl["label"] for lvl in data["risk_levels"]] == [
        "Low",
        "Moderate",
        "High",
        "Severe",
        "No Travel",
    ]


def test_each_route_has_summary_geometry_and_checkpoint_details(client, providers):
    route = post(client).json()["routes"][0]

    assert {"id", "label", "via", "distance_mi", "duration_s", "arrival"} <= set(route)
    assert {"severe_miles", "high_miles", "avg_risk", "max_level"} <= set(route["summary"])
    assert route["geometry"]["type"] == "LineString"
    first_lon, first_lat = route["geometry"]["coordinates"][0]
    assert (first_lat, first_lon) == (0.0, 0.0)  # GeoJSON order is lon, lat
    checkpoint = route["checkpoints"][1]
    assert {
        "index",
        "distance_mi",
        "lat",
        "lon",
        "eta",
        "level",
        "level_label",
        "reason",
        "wind_mph",
        "rain_in_hr",
        "snow_in_hr",
        "segment_miles",
        "load_escalated",
    } <= set(checkpoint)
    assert checkpoint["eta"].endswith("Z")
    assert "." not in checkpoint["eta"]  # whole seconds only


def test_response_is_plain_json_and_never_contains_the_api_key(client, providers):
    raw = post(client).content.decode()

    json.loads(raw)
    assert "ORS_API_KEY" not in raw


def test_places_can_be_given_as_text_and_are_geocoded(client, providers):
    response = post(client, origin="Denver", destination={"lat": 3.0, "lon": 5.0})

    assert response.status_code == 200


def test_unknown_place_text_is_a_validation_error(client, providers):
    routing, _ = providers
    routing.geocode = lambda text: []

    response = post(client, origin="Nowhereville")

    assert response.status_code == 400
    assert "Nowhereville" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("load_lb", -1),
        ("load_lb", 500_000),
        ("load_lb", "heavy"),
        ("interval_miles", 15),
        ("departure", "next tuesday"),
        ("origin", {"lat": 95, "lon": 0}),
        ("origin", {"lat": 0, "lon": 190}),
        ("origin", {"lon": 0}),
        ("destination", 42),
    ],
)
def test_invalid_input_is_rejected_with_field_errors(client, providers, field, value):
    response = post(client, **{field: value})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["fields"]


def test_missing_fields_are_reported(client, providers):
    response = client.post("/api/analyze", {}, format="json")

    assert response.status_code == 400
    assert {"origin", "destination", "departure", "load_lb", "interval_miles"} <= set(
        response.json()["error"]["fields"]
    )


def test_trip_level_problems_are_a_400_with_a_readable_message(client, providers):
    response = post(client, departure=(datetime.now(UTC) + timedelta(days=40)).isoformat())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_trip"
    assert "forecast" in response.json()["error"]["message"]


def test_provider_failure_is_a_502_with_a_safe_message(client, providers):
    routing, _ = providers
    routing.fail_base = True

    response = post(client)

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "provider_error",
        "message": "Routing service is unavailable",
    }


def test_get_is_not_allowed_on_analyze(client, providers):
    assert client.get("/api/analyze").status_code == 405


def test_geocode_returns_places(client, providers):
    response = client.get("/api/geocode", {"q": "Denver"})

    assert response.status_code == 200
    assert response.json() == {"places": [{"label": "Denver, Testville", "lat": 1.0, "lon": 2.0}]}


def test_geocode_requires_a_query_of_at_least_two_characters(client, providers):
    assert client.get("/api/geocode", {"q": "D"}).status_code == 400
    assert client.get("/api/geocode").status_code == 400


def test_geocode_provider_failure_is_a_502(client, providers):
    routing, _ = providers

    def broken(text):
        raise ProviderError("Routing service is busy, please try again shortly")

    routing.geocode = broken

    response = client.get("/api/geocode", {"q": "Denver"})

    assert response.status_code == 502


def test_base_route_not_found_is_a_400_not_a_gateway_error(client, providers):
    from api.providers.types import RouteNotFound

    routing, _ = providers
    routing.base_error = RouteNotFound("No drivable route found for those points")

    response = post(client)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_route"


def test_absurdly_large_coordinates_are_a_400_not_a_server_error(client, providers):
    response = post(client, origin={"lat": 10**400, "lon": 0})

    assert response.status_code == 400
    assert "origin" in response.json()["error"]["fields"]


@pytest.mark.parametrize("departure", ["0001-01-01T00:00+05:00", "9999-12-31T23:59-05:00"])
def test_departures_outside_a_sane_year_range_are_rejected(client, providers, departure):
    response = post(client, departure=departure)

    assert response.status_code == 400
    assert "departure" in response.json()["error"]["fields"]


def test_overlong_place_text_is_rejected(client, providers):
    response = post(client, origin="x" * 500)

    assert response.status_code == 400
    assert "origin" in response.json()["error"]["fields"]


def test_overlong_geocode_query_is_rejected(client, providers):
    assert client.get("/api/geocode", {"q": "x" * 500}).status_code == 400


def test_spoofed_forwarded_for_headers_do_not_bypass_the_throttle(client, providers):
    statuses = [
        client.post(
            "/api/analyze", body(), format="json", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}"
        ).status_code
        for i in range(12)
    ]

    assert statuses.count(429) >= 1


def heatmap_body(**overrides):
    payload = body(**overrides)
    payload.pop("interval_miles", None)  # the heatmap does not use the sampling interval
    return payload


def post_heatmap(client, **overrides):
    return client.post("/api/heatmap", heatmap_body(**overrides), format="json")


def test_heatmap_returns_a_corridor_grid_with_a_48_hour_series_per_point(client, providers):
    response = post_heatmap(client)

    assert response.status_code == 200
    data = response.json()
    assert data["hours"] == 49
    assert data["start"].endswith("Z")
    assert data["timezone"] == "UTC"
    assert [lvl["label"] for lvl in data["risk_levels"]][0] == "Low"
    assert len(data["points"]) > 10
    point = data["points"][0]
    assert set(point) == {"lat", "lon", "levels"}
    assert all(len(p["levels"]) == 49 for p in data["points"])
    assert data["warnings"] == []


def test_heatmap_payload_stays_small(client, providers):
    assert len(post_heatmap(client).content) < 40_000


def test_heatmap_accepts_the_same_places_and_validation_as_analyze(client, providers):
    response = post_heatmap(client, origin={"lat": 95, "lon": 0})

    assert response.status_code == 400
    assert "origin" in response.json()["error"]["fields"]


def test_heatmap_trip_problems_are_a_400(client, providers):
    response = post_heatmap(client, departure=(datetime.now(UTC) + timedelta(days=40)).isoformat())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_trip"


def test_heatmap_provider_failure_is_a_502(client, providers):
    routing, _ = providers
    routing.fail_base = True

    assert post_heatmap(client).status_code == 502


def test_heatmap_route_not_found_is_a_400(client, providers):
    from api.providers.types import RouteNotFound

    routing, _ = providers
    routing.base_error = RouteNotFound("No drivable route found for those points")

    response = post_heatmap(client)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_route"


def test_heatmap_is_post_only(client, providers):
    assert client.get("/api/heatmap").status_code == 405


def test_heatmap_is_rate_limited(client, providers):
    statuses = [post_heatmap(client).status_code for _ in range(12)]

    assert 429 in statuses
