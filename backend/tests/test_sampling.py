"""Checkpoint sampling along a route: distances, owned miles, and ETAs."""

from datetime import UTC, datetime, timedelta

import pytest

from engine.geo import MILES_PER_DEGREE_EQUATOR, haversine_miles
from engine.sampling import RouteGeometry, sample_checkpoints

DEPARTURE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
HOUR = 3600.0


def equator_route(miles: float, duration_s: float = HOUR, **kwargs) -> RouteGeometry:
    """A dead-straight route along the equator that is ``miles`` long."""
    degrees = miles / MILES_PER_DEGREE_EQUATOR
    return RouteGeometry(
        coordinates=((0.0, 0.0), (0.0, degrees / 2), (0.0, degrees)),
        duration_s=duration_s,
        **kwargs,
    )


def test_haversine_matches_known_distances():
    assert haversine_miles((0, 0), (0, 1)) == pytest.approx(69.09, abs=0.1)
    new_york, los_angeles = (40.7128, -74.0060), (34.0522, -118.2437)
    assert haversine_miles(new_york, los_angeles) == pytest.approx(2445, abs=15)


def test_haversine_of_identical_points_is_zero():
    assert haversine_miles((12.3, 45.6), (12.3, 45.6)) == 0


def test_checkpoints_every_interval_including_start_and_destination():
    checkpoints = sample_checkpoints(equator_route(100), 25, DEPARTURE)

    assert [round(c.distance_mi, 3) for c in checkpoints] == [0, 25, 50, 75, 100]
    assert [c.index for c in checkpoints] == [0, 1, 2, 3, 4]


def test_destination_is_always_a_checkpoint_when_distance_is_not_a_multiple():
    checkpoints = sample_checkpoints(equator_route(60), 25, DEPARTURE)

    assert [round(c.distance_mi, 3) for c in checkpoints] == [0, 25, 50, 60]


def test_route_shorter_than_interval_has_start_and_destination():
    checkpoints = sample_checkpoints(equator_route(8), 25, DEPARTURE)

    assert [round(c.distance_mi, 3) for c in checkpoints] == [0, 8]


def test_each_checkpoint_owns_miles_up_to_the_midpoints_between_neighbours():
    checkpoints = sample_checkpoints(equator_route(60), 25, DEPARTURE)

    owned = [round(c.segment_miles, 3) for c in checkpoints]
    assert owned == [12.5, 25, 17.5, 5]


@pytest.mark.parametrize("interval", [10, 25, 50])
@pytest.mark.parametrize("miles", [3, 49.5, 137.2, 480, 1203.7])
def test_owned_miles_always_sum_to_route_length(miles, interval):
    route = equator_route(miles)
    checkpoints = sample_checkpoints(route, interval, DEPARTURE)

    assert sum(c.segment_miles for c in checkpoints) == pytest.approx(miles, rel=1e-6)
    assert all(c.segment_miles > 0 for c in checkpoints)


def test_checkpoint_positions_lie_on_the_route():
    checkpoints = sample_checkpoints(equator_route(100), 25, DEPARTURE)

    middle = checkpoints[2]
    assert middle.lat == pytest.approx(0, abs=1e-9)
    assert middle.lon == pytest.approx(50 / MILES_PER_DEGREE_EQUATOR, rel=1e-6)


def test_positions_follow_bends_in_the_polyline():
    # 69.09 mi east along the equator, then 69.09 mi north.
    route = RouteGeometry(coordinates=((0, 0), (0, 1), (1, 1)), duration_s=2 * HOUR)

    checkpoints = sample_checkpoints(route, 100, DEPARTURE)

    assert [round(c.distance_mi) for c in checkpoints] == [0, 100, 138]
    corner_to_checkpoint = checkpoints[1]
    assert corner_to_checkpoint.lon == pytest.approx(1, abs=1e-3)
    assert corner_to_checkpoint.lat > 0.4  # already turned north


def test_eta_assumes_even_speed_without_a_duration_profile():
    checkpoints = sample_checkpoints(equator_route(100, duration_s=2 * HOUR), 50, DEPARTURE)

    assert checkpoints[0].eta == DEPARTURE
    assert checkpoints[1].eta == DEPARTURE + timedelta(hours=1)
    assert checkpoints[2].eta == DEPARTURE + timedelta(hours=2)
    assert checkpoints[1].elapsed_s == pytest.approx(HOUR)


def test_eta_uses_per_vertex_durations_when_provided():
    # First half is slow (600 s for 50 mi would be unrealistic but unambiguous),
    # second half takes the remaining 3000 s.
    route = equator_route(100, duration_s=3600, cumulative_duration_s=(0, 600, 3600))

    checkpoints = sample_checkpoints(route, 25, DEPARTURE)

    assert [round(c.elapsed_s) for c in checkpoints] == [0, 300, 600, 2100, 3600]


def test_eta_keeps_the_departure_timezone():
    pacific = datetime(2026, 11, 2, 8, 0, tzinfo=UTC).astimezone(UTC)
    checkpoints = sample_checkpoints(equator_route(50), 25, pacific)

    assert all(c.eta.tzinfo is not None for c in checkpoints)


def test_naive_departure_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        sample_checkpoints(equator_route(50), 25, datetime(2026, 11, 2, 8, 0))


@pytest.mark.parametrize("interval", [0, -5])
def test_non_positive_interval_is_rejected(interval):
    with pytest.raises(ValueError, match="interval"):
        sample_checkpoints(equator_route(50), interval, DEPARTURE)


def test_route_needs_at_least_two_coordinates():
    with pytest.raises(ValueError, match="coordinates"):
        RouteGeometry(coordinates=((0, 0),), duration_s=10)


def test_zero_length_route_is_rejected():
    route = RouteGeometry(coordinates=((5, 5), (5, 5)), duration_s=10)

    with pytest.raises(ValueError, match="length"):
        sample_checkpoints(route, 25, DEPARTURE)


def test_duration_profile_must_match_coordinates():
    with pytest.raises(ValueError, match="cumulative_duration_s"):
        RouteGeometry(coordinates=((0, 0), (0, 1)), duration_s=10, cumulative_duration_s=(0, 5, 10))


def test_negative_duration_is_rejected():
    with pytest.raises(ValueError, match="duration"):
        RouteGeometry(coordinates=((0, 0), (0, 1)), duration_s=-1)
