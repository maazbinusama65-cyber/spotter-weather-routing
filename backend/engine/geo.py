import math
from bisect import bisect_right

EARTH_RADIUS_MILES = 3958.7613
MILES_PER_DEGREE_EQUATOR = EARTH_RADIUS_MILES * math.pi / 180

LatLon = tuple[float, float]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def bearing_degrees(a: LatLon, b: LatLon) -> float:
    """Initial compass bearing from a to b, 0 = north, 90 = east."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return math.degrees(math.atan2(y, x)) % 360


def destination_point(origin: LatLon, bearing: float, miles: float) -> LatLon:
    lat1, lon1 = map(math.radians, origin)
    theta = math.radians(bearing)
    delta = miles / EARTH_RADIUS_MILES
    lat2 = math.asin(
        math.sin(lat1) * math.cos(delta) + math.cos(lat1) * math.sin(delta) * math.cos(theta)
    )
    lon2 = lon1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def point_at_distance(
    coordinates: tuple[LatLon, ...], cumulative: tuple[float, ...], distance: float
) -> tuple[float, float, int, float]:
    """Latitude, longitude, segment index and fraction into it, ``distance`` miles along."""
    last_vertex = len(cumulative) - 1
    segment = min(max(bisect_right(cumulative, distance) - 1, 0), last_vertex - 1)
    seg_start, seg_end = cumulative[segment], cumulative[segment + 1]
    fraction = 0.0 if seg_end == seg_start else (distance - seg_start) / (seg_end - seg_start)
    (lat1, lon1), (lat2, lon2) = coordinates[segment], coordinates[segment + 1]
    return lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction, segment, fraction


def cumulative_miles(coordinates: tuple[LatLon, ...]) -> tuple[float, ...]:
    """Distance from the first vertex to each vertex along the polyline."""
    total = 0.0
    cumulative = [0.0]
    for previous, current in zip(coordinates, coordinates[1:], strict=False):
        total += haversine_miles(previous, current)
        cumulative.append(total)
    return tuple(cumulative)
