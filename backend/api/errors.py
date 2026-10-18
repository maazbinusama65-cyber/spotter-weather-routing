"""One error envelope for every API failure: {"error": {"code", "message", "fields"?}}."""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def error_response(code: str, message: str, http_status: int, fields: dict | None = None):
    error: dict = {"code": code, "message": message}
    if fields:
        error["fields"] = fields
    return Response({"error": error}, status=http_status)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
        fields = {name: _first_message(detail) for name, detail in exc.detail.items()}
        message = next(iter(fields.values()), "Invalid request")
        return error_response("validation_error", message, response.status_code, fields)

    message = str(exc.detail) if isinstance(exc, APIException) else "Request failed"
    code = getattr(exc, "default_code", "error")
    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        message = "Too many requests, please slow down"
    return error_response(code, message, response.status_code)


def _first_message(detail) -> str:
    if isinstance(detail, list | tuple) and detail:
        return _first_message(detail[0])
    if isinstance(detail, dict) and detail:
        return _first_message(next(iter(detail.values())))
    return str(detail)
