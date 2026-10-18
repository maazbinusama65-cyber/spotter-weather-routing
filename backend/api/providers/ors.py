"""OpenRouteService adapter: HGV routing and geocoding.

The API key travels in the Authorization header, never in the URL, and never reaches
the browser.
"""

import logging
from collections.abc import Sequence

import httpx

from engine.geo import LatLon, haversine_miles
from engine.sampling import RouteGeometry

from .types import Place, ProviderError, RouteNotFound, RouteOption

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openrouteservice.org"
HGV_PROFILE = "driving-hgv"
GEOCODE_RESULTS = 5
MAX_VIA_ROADS = 3
# ORS error codes meaning "no route / no routable point" rather than a bad request
NO_ROUTE_ERROR_CODES = {2009, 2010}


class OrsClient:
    def __init__(
        self,
        api_key: str,
        timeout: float = 10.0,
        http: httpx.Client | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=timeout)
        self._base_url = base_url

    def route(self, waypoints: Sequence[LatLon]) -> RouteOption:
        body = {
            "coordinates": [[lon, lat] for lat, lon in waypoints],
            "instructions": True,
            # -1 lets via points snap to the nearest road however far away it is
            "radiuses": [-1] * len(waypoints),
        }
        data = self._request("POST", f"/v2/directions/{HGV_PROFILE}/geojson", json=body)
        try:
            return _parse_route(data)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("Routing service returned an unexpected response") from error

    def geocode(self, text: str) -> list[Place]:
        data = self._request(
            "GET",
            "/geocode/search",
            params={"text": text, "size": GEOCODE_RESULTS},
            unroutable_is_not_found=False,
        )
        return _parse_places(data)

    def _request(self, method: str, path: str, unroutable_is_not_found: bool = True, **kwargs):
        if not self._api_key:
            logger.error("ORS_API_KEY is not set; routing is disabled")
            raise ProviderError("Routing service is not configured")
        try:
            response = self._http.request(
                method,
                self._base_url + path,
                headers={"Authorization": self._api_key},
                **kwargs,
            )
        except httpx.TimeoutException as error:
            raise ProviderError("Routing service timed out") from error
        except httpx.HTTPError as error:
            raise ProviderError("Routing service is unreachable") from error

        status = response.status_code
        if status in (401, 403):
            # Operator problem: details go to the log, users only see a generic message.
            logger.error("OpenRouteService rejected the API key (HTTP %s)", status)
            raise ProviderError("Routing service is unavailable")
        if status == 429:
            raise ProviderError("Routing service is busy, please try again shortly")
        if status >= 400:
            code = _error_code(response)
            if unroutable_is_not_found and (status == 404 or code in NO_ROUTE_ERROR_CODES):
                raise RouteNotFound("No drivable route found for those points")
            logger.warning("OpenRouteService HTTP %s, error code %s", status, code)
            raise ProviderError("Routing service is unavailable")
        try:
            return response.json()
        except ValueError as error:
            raise ProviderError("Routing service returned an unexpected response") from error


def _error_code(response: httpx.Response) -> int | None:
    try:
        error = response.json().get("error")
        code = error.get("code") if isinstance(error, dict) else None
    except (ValueError, AttributeError):
        return None
    return code if isinstance(code, int) else None


def _parse_route(data: dict) -> RouteOption:
    feature = data["features"][0]
    coordinates: tuple[LatLon, ...] = tuple(
        (point[1], point[0]) for point in feature["geometry"]["coordinates"]
    )
    properties = feature["properties"]
    duration = float(properties["summary"]["duration"])
    steps = [step for segment in properties.get("segments", []) for step in segment["steps"]]

    geometry = RouteGeometry(
        coordinates=coordinates,
        duration_s=duration,
        cumulative_duration_s=_vertex_durations(coordinates, steps),
    )
    return RouteOption(geometry=geometry, via=_main_roads(steps))


def _vertex_durations(
    coordinates: tuple[LatLon, ...], steps: list[dict]
) -> tuple[float, ...] | None:
    """Elapsed seconds at every vertex, spreading each step's duration by distance."""
    if not steps:
        return None
    profile = [0.0] * len(coordinates)
    expected_start = 0
    for step in steps:
        start, end = step["way_points"]
        if start != expected_start or end >= len(coordinates):
            return None
        legs = [
            haversine_miles(coordinates[i - 1], coordinates[i]) for i in range(start + 1, end + 1)
        ]
        total = sum(legs)
        travelled = 0.0
        for offset, leg in enumerate(legs, start=1):
            travelled += leg
            share = travelled / total if total else offset / len(legs)
            profile[start + offset] = profile[start] + float(step["duration"]) * share
        expected_start = end
    return tuple(profile) if expected_start == len(coordinates) - 1 else None


def _main_roads(steps: list[dict]) -> str:
    distances: dict[str, float] = {}
    for step in steps:
        name = (step.get("name") or "").strip()
        if name and name != "-":
            distances[name] = distances.get(name, 0.0) + float(step.get("distance", 0))
    longest = sorted(distances, key=lambda n: -distances[n])[:MAX_VIA_ROADS]
    in_route_order = [name for name in distances if name in longest]
    return ", ".join(in_route_order)


def _parse_places(data: dict) -> list[Place]:
    places = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        label = (feature.get("properties") or {}).get("label")
        if not coordinates or len(coordinates) < 2 or not label:
            continue
        places.append(Place(label=label, lat=coordinates[1], lon=coordinates[0]))
    return places
