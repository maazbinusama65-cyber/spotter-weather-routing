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
