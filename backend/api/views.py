from django.core.cache import caches
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .errors import error_response
from .providers.factory import get_providers
from .providers.types import ProviderError, RouteNotFound, RoutingProvider
from .serializers import AnalyzeRequestSerializer, PlaceInput, TripRequestSerializer
from .services.heatmap import build_heatmap
from .services.present import present_analysis, present_heatmap
from .services.trip import TripRequest, TripValidationError, analyze_trip

MIN_GEOCODE_QUERY = 2
MAX_GEOCODE_QUERY = 200


class _Throttle(AnonRateThrottle):
    cache = caches["throttle"]  # separate store so cache churn cannot reset counters


class AnalyzeThrottle(_Throttle):
    scope = "analyze"  # each analysis makes several upstream calls


class HeatmapThrottle(_Throttle):
    scope = "heatmap"  # fetches weather for up to 150 locations


class GeocodeThrottle(_Throttle):
    scope = "geocode"


@api_view(["GET"])
@throttle_classes([])
def health(request):
    """Liveness probe used by the host and the uptime pinger."""
    return Response({"status": "ok"})


HEATMAP_INTERVAL_MILES = 25  # the heatmap samples its own grid; the interval is unused


def _run_trip(request, serializer_class, action):
    """Validate the body, resolve places, run ``action`` and map failures to HTTP."""
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    routing, weather = get_providers()
    try:
        trip = TripRequest(
            origin=_resolve_place(routing, data["origin"]),
            destination=_resolve_place(routing, data["destination"]),
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_miles=data.get("interval_miles", HEATMAP_INTERVAL_MILES),
        )
        return Response(action(trip, routing, weather))
    except TripValidationError as error:
        return error_response("invalid_trip", str(error), status.HTTP_400_BAD_REQUEST)
    except RouteNotFound as error:
        return error_response("no_route", str(error), status.HTTP_400_BAD_REQUEST)
    except ProviderError as error:
        return error_response("provider_error", str(error), status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
@throttle_classes([AnalyzeThrottle])
def analyze(request):
    return _run_trip(
        request,
        AnalyzeRequestSerializer,
        lambda trip, routing, weather: present_analysis(analyze_trip(trip, routing, weather)),
    )


@api_view(["POST"])
@throttle_classes([HeatmapThrottle])
def heatmap(request):
    return _run_trip(
        request,
        TripRequestSerializer,
        lambda trip, routing, weather: present_heatmap(build_heatmap(trip, routing, weather)),
    )


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request):
    query = request.query_params.get("q", "").strip()
    if len(query) > MAX_GEOCODE_QUERY:
        return error_response(
            "validation_error",
            "Search text is too long",
            status.HTTP_400_BAD_REQUEST,
            {"q": "Search text is too long"},
        )
    if len(query) < MIN_GEOCODE_QUERY:
        return error_response(
            "validation_error",
            f"Type at least {MIN_GEOCODE_QUERY} characters",
            status.HTTP_400_BAD_REQUEST,
            {"q": f"Type at least {MIN_GEOCODE_QUERY} characters"},
        )
    routing, _ = get_providers()
    try:
        places = routing.geocode(query)
    except ProviderError as error:
        return error_response("provider_error", str(error), status.HTTP_502_BAD_GATEWAY)
    return Response({"places": [{"label": p.label, "lat": p.lat, "lon": p.lon} for p in places]})


def _resolve_place(routing: RoutingProvider, place: PlaceInput) -> tuple[float, float]:
    if place.lat is not None and place.lon is not None:
        return place.lat, place.lon
    matches = routing.geocode(place.text)
    if not matches:
        raise TripValidationError(f"Could not find a place matching '{place.text[:60]}'")
    return matches[0].lat, matches[0].lon
