import math

EARTH_RADIUS_MILES = 3958.7613
MILES_PER_DEGREE_EQUATOR = EARTH_RADIUS_MILES * math.pi / 180

LatLon = tuple[float, float]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    d_lat, d_lon = lat2 - lat1, lon2 - lon1
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(coordinates: tuple[LatLon, ...]) -> tuple[float, ...]:
    """Distance from the first vertex to each vertex along the polyline."""
    total = 0.0
    cumulative = [0.0]
    for previous, current in zip(coordinates, coordinates[1:], strict=False):
        total += haversine_miles(previous, current)
        cumulative.append(total)
    return tuple(cumulative)
