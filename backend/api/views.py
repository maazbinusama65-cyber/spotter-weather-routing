from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response


@api_view(["GET"])
@throttle_classes([])
def health(request):
    """Liveness probe used by the host and the uptime pinger."""
    return Response({"status": "ok"})
