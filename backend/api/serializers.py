"""Request validation for the HTTP API."""

import math
from dataclasses import dataclass
from datetime import datetime

from rest_framework import serializers

ALLOWED_INTERVALS = (10, 25, 50)
MAX_LOAD_LB = 100_000
MIN_PLACE_TEXT = 2
MAX_PLACE_TEXT = 200
MIN_DEPARTURE_YEAR, MAX_DEPARTURE_YEAR = 2000, 2100


@dataclass(frozen=True)
class PlaceInput:
    """Either coordinates (from a picked suggestion) or free text to geocode."""

    lat: float | None = None
    lon: float | None = None
    label: str = ""
    text: str = ""


def _coordinate(data: dict, key: str, limit: float) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise serializers.ValidationError(f"{key} must be a number")
    if isinstance(value, float) and math.isnan(value):
        raise serializers.ValidationError(f"{key} must be a number")
    if abs(value) > limit:
        raise serializers.ValidationError(f"{key} must be between -{limit:g} and {limit:g}")
    return float(value)


class PlaceField(serializers.Field):
    def to_internal_value(self, data) -> PlaceInput:
        if isinstance(data, str):
            text = data.strip()
            if len(text) < MIN_PLACE_TEXT:
                raise serializers.ValidationError("Enter a place name or choose a suggestion")
            if len(text) > MAX_PLACE_TEXT:
                raise serializers.ValidationError("Place text is too long")
            return PlaceInput(text=text)
        if isinstance(data, dict):
            return PlaceInput(
                lat=_coordinate(data, "lat", 90),
                lon=_coordinate(data, "lon", 180),
                label=str(data.get("label", ""))[:200],
            )
        raise serializers.ValidationError("Expected a place with lat and lon, or place text")

    def to_representation(self, value):  # pragma: no cover - requests only
        return value


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = PlaceField()
    destination = PlaceField()
    departure = serializers.CharField()
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.IntegerField()

    def validate_departure(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise serializers.ValidationError(
                "Use an ISO date and time, for example 2026-11-02T08:00"
            ) from error
        if not MIN_DEPARTURE_YEAR <= parsed.year <= MAX_DEPARTURE_YEAR:
            raise serializers.ValidationError("Departure year is out of range")
        return parsed

    def validate_interval_miles(self, value: int) -> int:
        if value not in ALLOWED_INTERVALS:
            allowed = ", ".join(str(v) for v in ALLOWED_INTERVALS)
            raise serializers.ValidationError(f"Choose one of: {allowed} miles")
        return value
