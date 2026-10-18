from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .errors import error_response
from .providers.factory import get_providers
from .providers.types import ProviderError, RoutingProvider
from .serializers import AnalyzeRequestSerializer, PlaceInput
from .services.present import present_analysis
from .services.trip import TripRequest, TripValidationError, analyze_trip

MIN_GEOCODE_QUERY = 2


class AnalyzeThrottle(AnonRateThrottle):
    scope = "analyze"  # each analysis makes several upstream calls


class GeocodeThrottle(AnonRateThrottle):
    scope = "geocode"


@api_view(["GET"])
@throttle_classes([])
def health(request):
    """Liveness probe used by the host and the uptime pinger."""
    return Response({"status": "ok"})


@api_view(["POST"])
@throttle_classes([AnalyzeThrottle])
def analyze(request):
    serializer = AnalyzeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    routing, weather = get_providers()
    try:
        trip = TripRequest(
            origin=_resolve_place(routing, data["origin"]),
            destination=_resolve_place(routing, data["destination"]),
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_miles=data["interval_miles"],
        )
        analysis = analyze_trip(trip, routing, weather)
    except TripValidationError as error:
        return error_response("invalid_trip", str(error), status.HTTP_400_BAD_REQUEST)
    except ProviderError as error:
        return error_response("provider_error", str(error), status.HTTP_502_BAD_GATEWAY)
    return Response(present_analysis(analysis))


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request):
    query = request.query_params.get("q", "").strip()
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
        raise TripValidationError(f"Could not find a place matching '{place.text}'")
    return matches[0].lat, matches[0].lon
