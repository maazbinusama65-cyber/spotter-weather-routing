"""Generating diverse route candidates and choosing up to three distinct ones."""

import pytest

from engine.candidates import (
    generate_via_points,
    overlap_fraction,
    select_distinct_routes,
    via_point,
)
from engine.geo import MILES_PER_DEGREE_EQUATOR, bearing_degrees, destination_point
from engine.sampling import RouteGeometry

DEG = 1 / MILES_PER_DEGREE_EQUATOR  # degrees per mile along the equator


def eastbound(miles: float, lat: float = 0.0) -> tuple[tuple[float, float], ...]:
    return ((lat, 0.0), (lat, miles * DEG / 2), (lat, miles * DEG))


def geometry(coords, duration_s=3600.0) -> RouteGeometry:
    return RouteGeometry(coordinates=tuple(coords), duration_s=duration_s)


def test_bearing_of_cardinal_directions():
    assert bearing_degrees((0, 0), (0, 1)) == pytest.approx(90)
    assert bearing_degrees((0, 0), (1, 0)) == pytest.approx(0)
    assert bearing_degrees((0, 0), (0, -1)) == pytest.approx(270)


def test_destination_point_round_trips_with_distance():
    lat, lon = destination_point((0, 0), 90, MILES_PER_DEGREE_EQUATOR)

    assert lat == pytest.approx(0, abs=1e-9)
    assert lon == pytest.approx(1, abs=1e-6)


def test_via_point_left_of_eastbound_route_is_north_and_right_is_south():
    route = eastbound(200)

    left = via_point(route, fraction=0.5, offset_miles=20, side="left")
    right = via_point(route, fraction=0.5, offset_miles=20, side="right")

    assert left[0] == pytest.approx(20 * DEG, rel=1e-3)
    assert right[0] == pytest.approx(-20 * DEG, rel=1e-3)
    assert left[1] == pytest.approx(100 * DEG, rel=1e-3)


def test_generate_via_points_makes_left_and_right_points_per_fraction():
    points = generate_via_points(eastbound(200), fractions=(0.33, 0.66), offset_miles=15)

    assert len(points) == 4
    assert {round(p[0] * MILES_PER_DEGREE_EQUATOR) for p in points} == {15, -15}


def test_identical_routes_overlap_fully():
    route = eastbound(100)

    assert overlap_fraction(route, route) == pytest.approx(1.0)


def test_parallel_routes_far_apart_do_not_overlap():
    assert overlap_fraction(eastbound(100), eastbound(100, lat=0.5)) == 0


def test_routes_sharing_half_their_length_overlap_about_half():
    a = ((0, 0), (0, 100 * DEG))
    b = ((0, 0), (0, 50 * DEG), (0.5, 50 * DEG), (0.5, 100 * DEG))

    assert 0.3 <= overlap_fraction(a, b) <= 0.6


def test_overlap_is_symmetric():
    a = ((0, 0), (0, 100 * DEG))
    b = ((0, 0), (0, 40 * DEG), (0.4, 70 * DEG), (0, 100 * DEG))

    assert overlap_fraction(a, b) == pytest.approx(overlap_fraction(b, a))


def test_near_duplicate_of_base_is_dropped_and_distinct_route_kept():
    base = geometry(eastbound(200))
    near_duplicate = geometry(eastbound(200, lat=0.005))  # about 0.3 mi away
    distinct = geometry(((0, 0), (0.4, 100 * DEG), (0, 200 * DEG)), duration_s=4000)

    chosen = select_distinct_routes([base, near_duplicate, distinct])

    assert chosen == [0, 2]


def test_base_route_is_always_first_and_at_most_three_are_returned():
    base = geometry(eastbound(200))
    detours = [
        geometry(((0, 0), (lat, 100 * DEG), (0, 200 * DEG)), duration_s=4000)
        for lat in (0.3, -0.3, 0.6, -0.6)
    ]

    chosen = select_distinct_routes([base, *detours])

    assert chosen[0] == 0
    assert len(chosen) == 3


def test_most_different_candidates_are_preferred():
    base = geometry(eastbound(200))
    slight = geometry(((0, 0), (0.12, 100 * DEG), (0, 200 * DEG)))
    bigger = geometry(((0, 0), (-0.4, 100 * DEG), (0, 200 * DEG)))
    biggest = geometry(((0, 0), (0.8, 100 * DEG), (0, 200 * DEG)))

    chosen = select_distinct_routes([base, slight, bigger, biggest], max_routes=2)

    assert chosen == [0, 3]


def test_absurdly_long_detours_are_rejected():
    base = geometry(eastbound(200))
    huge_detour = geometry(((0, 0), (3, 100 * DEG), (0, 200 * DEG)))  # many times longer

    assert select_distinct_routes([base, huge_detour]) == [0]


def test_single_candidate_returns_just_the_base():
    assert select_distinct_routes([geometry(eastbound(50))]) == [0]


def test_no_candidates_is_an_error():
    with pytest.raises(ValueError, match="candidate"):
        select_distinct_routes([])
