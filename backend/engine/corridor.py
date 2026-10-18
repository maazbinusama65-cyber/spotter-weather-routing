"""Sample the trip corridor (all candidate routes) for the weather heatmap."""

from collections.abc import Sequence

from .geo import LatLon, cumulative_miles, point_at_distance
from .sampling import RouteGeometry

DEFAULT_MIN_SPACING_MILES = 25.0
DEFAULT_TARGET_PER_ROUTE = 60
DEFAULT_MAX_POINTS = 150
DEFAULT_CELL_DECIMALS = 1  # 0.1 degree weather cells, roughly 7 miles
_END_TOLERANCE_MILES = 1e-9


def corridor_points(
    routes: Sequence[RouteGeometry],
    min_spacing_miles: float = DEFAULT_MIN_SPACING_MILES,
    target_per_route: int = DEFAULT_TARGET_PER_ROUTE,
    max_points: int = DEFAULT_MAX_POINTS,
    cell_decimals: int = DEFAULT_CELL_DECIMALS,
) -> list[LatLon]:
    """Grid-cell centres along every route, deduplicated and capped.

    Spacing widens on long routes so each contributes about ``target_per_route`` points,
    and the whole set is thinned evenly to ``max_points``. That bounds how many weather
    locations one heatmap needs, whatever the trip length.
    """
    unique: dict[LatLon, None] = {}  # insertion-ordered set
    for route in routes:
        coordinates = tuple(route.coordinates)
        cumulative = cumulative_miles(coordinates)
        total = cumulative[-1]
        spacing = max(min_spacing_miles, total / target_per_route)
        for distance in _distances(total, spacing):
            lat, lon, _, _ = point_at_distance(coordinates, cumulative, distance)
            unique.setdefault((round(lat, cell_decimals), round(lon, cell_decimals)))
    return _thin(list(unique), max_points)


def _distances(total: float, spacing: float) -> list[float]:
    regular = int((total - _END_TOLERANCE_MILES) // spacing)
    return [i * spacing for i in range(regular + 1)] + [total]


def _thin(points: list[LatLon], max_points: int) -> list[LatLon]:
    if len(points) <= max_points:
        return points
    if max_points <= 1:
        return points[:max_points]
    # Spread over the whole range so both the origin and the final point survive.
    last = len(points) - 1
    return [points[round(i * last / (max_points - 1))] for i in range(max_points)]
