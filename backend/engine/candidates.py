"""Build diverse route candidates and pick up to three distinct ones.

Routing providers only offer alternatives for short trips, so for long truck routes we
route through offset "via" points around the fastest route and keep the results that
genuinely differ from it.
"""

import math
from collections.abc import Sequence
from typing import Literal

from .geo import (
    LatLon,
    bearing_degrees,
    cumulative_miles,
    destination_point,
    haversine_miles,
    point_at_distance,
)
from .sampling import RouteGeometry

DEFAULT_TOLERANCE_MILES = 3.0
DEFAULT_MAX_OVERLAP = 0.85
DEFAULT_MAX_DISTANCE_RATIO = 1.6

_DENSIFY_SPACING_MILES = 1.0
_SAMPLE_SPACING_MILES = 2.0
_MAX_SAMPLES = 150
_GRID_CELL_DEGREES = 0.1  # lookups check the 3x3 cells around a point, so tolerance < ~7 mi


def via_point(
    coordinates: Sequence[LatLon],
    fraction: float,
    offset_miles: float,
    side: Literal["left", "right"],
) -> LatLon:
    """A point ``offset_miles`` to the left or right of the route ``fraction`` of the way along."""
    coords = tuple(coordinates)
    cumulative = cumulative_miles(coords)
    lat, lon, segment, _ = point_at_distance(coords, cumulative, fraction * cumulative[-1])
    heading = bearing_degrees(coords[segment], coords[segment + 1])
    turn = -90 if side == "left" else 90
    return destination_point((lat, lon), (heading + turn) % 360, offset_miles)


def generate_via_points(
    coordinates: Sequence[LatLon],
    fractions: Sequence[float] = (0.35, 0.65),
    offset_miles: float = 25.0,
) -> list[LatLon]:
    return [
        via_point(coordinates, fraction, offset_miles, side)
        for fraction in fractions
        for side in ("left", "right")
    ]


def overlap_fraction(
    a: Sequence[LatLon], b: Sequence[LatLon], tolerance_miles: float = DEFAULT_TOLERANCE_MILES
) -> float:
    """How much two routes share, 0 to 1. Symmetric: the smaller of each route's coverage
    by the other, so a long loop around a short route is not a duplicate of it."""
    a_coords, b_coords = tuple(a), tuple(b)
    return min(
        _coverage(a_coords, b_coords, tolerance_miles),
        _coverage(b_coords, a_coords, tolerance_miles),
    )


def select_distinct_routes(
    routes: Sequence[RouteGeometry],
    max_routes: int = 3,
    max_overlap: float = DEFAULT_MAX_OVERLAP,
    max_distance_ratio: float = DEFAULT_MAX_DISTANCE_RATIO,
) -> list[int]:
    """Indexes of the routes to offer. ``routes[0]`` is the base (fastest) route and is
    always first; the rest are chosen greedily, most different from those already chosen."""
    if not routes:
        raise ValueError("at least one route candidate is required")

    lengths = [cumulative_miles(r.coordinates)[-1] for r in routes]
    eligible = [i for i in range(1, len(routes)) if lengths[i] <= max_distance_ratio * lengths[0]]
    chosen = [0]
    cache: dict[tuple[int, int], float] = {}

    def similarity(i: int, j: int) -> float:
        key = (min(i, j), max(i, j))
        if key not in cache:
            cache[key] = overlap_fraction(routes[i].coordinates, routes[j].coordinates)
        return cache[key]

    while len(chosen) < max_routes:
        scored = [(max(similarity(i, c) for c in chosen), i) for i in eligible if i not in chosen]
        scored = [(s, i) for s, i in scored if s < max_overlap]
        if not scored:
            break
        chosen.append(min(scored)[1])
    return chosen


def _coverage(source: tuple[LatLon, ...], target: tuple[LatLon, ...], tolerance: float) -> float:
    """Fraction of points sampled along ``source`` that lie within tolerance of ``target``."""
    index = _PointIndex(_densify(target, _DENSIFY_SPACING_MILES))
    samples = _sample(source)
    near = sum(1 for point in samples if index.has_within(point, tolerance))
    return near / len(samples)


def _points_along(coords: tuple[LatLon, ...], distances: Sequence[float]) -> list[LatLon]:
    cumulative = cumulative_miles(coords)
    points = []
    for distance in distances:
        lat, lon, _, _ = point_at_distance(coords, cumulative, distance)
        points.append((lat, lon))
    return points


def _densify(coords: tuple[LatLon, ...], spacing: float) -> list[LatLon]:
    total = cumulative_miles(coords)[-1]
    steps = max(1, math.ceil(total / spacing))
    return _points_along(coords, [total * i / steps for i in range(steps + 1)])


def _sample(coords: tuple[LatLon, ...]) -> list[LatLon]:
    total = cumulative_miles(coords)[-1]
    count = min(_MAX_SAMPLES, max(2, int(total / _SAMPLE_SPACING_MILES) + 1))
    return _points_along(coords, [total * i / (count - 1) for i in range(count)])


class _PointIndex:
    """Grid index so "is any point within N miles" doesn't scan every point."""

    def __init__(self, points: Sequence[LatLon]) -> None:
        self._cells: dict[tuple[int, int], list[LatLon]] = {}
        for point in points:
            self._cells.setdefault(self._cell(point), []).append(point)

    @staticmethod
    def _cell(point: LatLon) -> tuple[int, int]:
        return math.floor(point[0] / _GRID_CELL_DEGREES), math.floor(point[1] / _GRID_CELL_DEGREES)

    def has_within(self, point: LatLon, miles: float) -> bool:
        row, col = self._cell(point)
        return any(
            haversine_miles(point, candidate) <= miles
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
            for candidate in self._cells.get((row + d_row, col + d_col), ())
        )
