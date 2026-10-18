"""Route recommendation: fewest Severe miles, then High miles, then average risk, then time."""

import pytest

from engine.analysis import RouteSummary
from engine.ranking import rank_routes
from engine.risk import RiskLevel


def summary(
    route_id: str,
    *,
    no_travel=0.0,
    severe=0.0,
    high=0.0,
    avg_risk=0.5,
    duration_s=3600.0,
    unknown=0.0,
) -> RouteSummary:
    return RouteSummary(
        route_id=route_id,
        label=f"Route {route_id.upper()}",
        distance_mi=100,
        duration_s=duration_s,
        no_travel_miles=no_travel,
        severe_miles=severe,
        high_miles=high,
        moderate_miles=0,
        low_miles=100 - no_travel - severe - high - unknown,
        unknown_miles=unknown,
        avg_risk=avg_risk,
        max_level=RiskLevel.LOW,
    )


def test_fewest_severe_miles_wins_even_if_slower_and_higher_on_everything_else():
    a = summary("a", severe=20, high=0, avg_risk=0.1, duration_s=3000)
    b = summary("b", severe=5, high=80, avg_risk=2.0, duration_s=9000)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"
    assert result.ranking == ("b", "a")
    assert "Severe" in result.reason


def test_high_miles_decide_when_severe_miles_tie():
    a = summary("a", severe=10, high=30)
    b = summary("b", severe=10, high=12, duration_s=9000)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"
    assert "High" in result.reason


def test_average_risk_decides_when_severe_and_high_tie():
    a = summary("a", avg_risk=0.9)
    b = summary("b", avg_risk=0.4, duration_s=9000)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"
    assert "average risk" in result.reason.lower()


def test_travel_time_decides_when_weather_risk_ties():
    a = summary("a", duration_s=7200)
    b = summary("b", duration_s=6000)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"
    assert "fastest" in result.reason.lower()


def test_no_travel_exposure_ranks_below_any_route_without_it():
    risky = summary("risky", no_travel=5, severe=0, high=0)
    messy = summary("messy", no_travel=0, severe=90, high=10)

    result = rank_routes([risky, messy])

    assert result.best_route_id == "messy"
    assert "No Travel" in result.reason


def test_all_routes_blocked_still_recommends_least_bad_with_warning():
    a = summary("a", no_travel=40)
    b = summary("b", no_travel=10)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"
    assert result.all_blocked is True


def test_not_blocked_when_any_route_is_clear():
    result = rank_routes([summary("a", no_travel=3), summary("b")])

    assert result.all_blocked is False


def test_tiny_float_differences_do_not_decide_the_winner():
    a = summary("a", severe=10.00001, duration_s=7000)
    b = summary("b", severe=10.0, duration_s=6000)

    result = rank_routes([a, b])

    assert result.best_route_id == "b"  # severe miles equal at 0.1 mi resolution, b is faster


def test_full_tie_keeps_input_order_and_says_so():
    result = rank_routes([summary("a"), summary("b")])

    assert result.ranking == ("a", "b")
    assert "equal" in result.reason.lower()


def test_ranking_of_three_routes_is_ordered_best_to_worst():
    a = summary("a", severe=30)
    b = summary("b", severe=0, high=40)
    c = summary("c", severe=10)

    result = rank_routes([a, b, c])

    assert result.ranking == ("b", "c", "a")


def test_single_route_is_recommended_without_comparison():
    result = rank_routes([summary("only")])

    assert result.best_route_id == "only"
    assert result.ranking == ("only",)
    assert "only" in result.reason.lower()


def test_no_routes_is_an_error():
    with pytest.raises(ValueError, match="route"):
        rank_routes([])
