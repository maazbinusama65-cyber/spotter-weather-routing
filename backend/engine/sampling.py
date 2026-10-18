"""Place weather checkpoints along a route and work out when the truck reaches each one."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .geo import LatLon, cumulative_miles, point_at_distance

_END_TOLERANCE_MILES = 1e-9


@dataclass(frozen=True)
class RouteGeometry:
    """A route as the engine sees it: a polyline in (lat, lon) and how long it takes.

    ``cumulative_duration_s`` optionally gives elapsed seconds at each vertex (as
    reported by the routing provider). Without it, speed is assumed constant.
    """

    coordinates: tuple[LatLon, ...]
    duration_s: float
    cumulative_duration_s: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if len(self.coordinates) < 2:
            raise ValueError("a route needs at least two coordinates")
        if self.duration_s < 0:
            raise ValueError("duration_s must not be negative")
        profile = self.cumulative_duration_s
        if profile is not None and len(profile) != len(self.coordinates):
            raise ValueError("cumulative_duration_s must have one value per coordinate")


@dataclass(frozen=True)
class Checkpoint:
    index: int
    distance_mi: float  # from the origin along the route
    lat: float
    lon: float
    segment_miles: float  # route miles this checkpoint's weather stands for
    elapsed_s: float
    eta: datetime


def sample_checkpoints(
    route: RouteGeometry, interval_miles: float, departure: datetime
) -> tuple[Checkpoint, ...]:
    """Checkpoints at the origin, every ``interval_miles``, and the destination.

    Each checkpoint owns the miles out to the midpoint between it and its neighbours,
    so owned miles always add up to the route length whatever the interval.
    """
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")
    if departure.tzinfo is None:
        raise ValueError("departure must be timezone-aware")

    cumulative = cumulative_miles(route.coordinates)
    total = cumulative[-1]
    if total <= 0:
        raise ValueError("route length must be greater than zero")

    distances = _checkpoint_distances(total, interval_miles)
    owned = _owned_miles(distances, total)

    checkpoints = []
    for index, (distance, segment_miles) in enumerate(zip(distances, owned, strict=True)):
        lat, lon, elapsed = _locate(route, cumulative, distance)
        checkpoints.append(
            Checkpoint(
                index=index,
                distance_mi=distance,
                lat=lat,
                lon=lon,
                segment_miles=segment_miles,
                elapsed_s=elapsed,
                eta=departure + timedelta(seconds=elapsed),
            )
        )
    return tuple(checkpoints)


def _checkpoint_distances(total: float, interval: float) -> list[float]:
    regular = int((total - _END_TOLERANCE_MILES) // interval)
    return [i * interval for i in range(regular + 1)] + [total]


def _owned_miles(distances: list[float], total: float) -> list[float]:
    midpoints = [(a + b) / 2 for a, b in zip(distances, distances[1:], strict=False)]
    starts = [0.0, *midpoints]
    ends = [*midpoints, total]
    return [end - start for start, end in zip(starts, ends, strict=True)]


def _locate(
    route: RouteGeometry, cumulative: tuple[float, ...], distance: float
) -> tuple[float, float, float]:
    """Latitude, longitude and elapsed seconds at ``distance`` miles along the route."""
    lat, lon, segment, fraction = point_at_distance(route.coordinates, cumulative, distance)

    profile = route.cumulative_duration_s
    if profile is None:
        elapsed = route.duration_s * distance / cumulative[-1]
    else:
        elapsed = profile[segment] + (profile[segment + 1] - profile[segment]) * fraction
    return lat, lon, elapsed
