"""Pick the recommended route.

Strict lexicographic preference, as the assessment specifies:
No Travel miles, then Severe miles, then High miles, then average risk, then time.
No Travel exposure is checked first so a route the truck cannot drive never beats one
it can. Values are rounded (0.1 mi, 0.001 risk, 1 s) so float noise cannot pick a winner.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .analysis import RouteSummary

_KEYS = ("no_travel", "severe", "high", "avg_risk", "duration")


@dataclass(frozen=True)
class Recommendation:
    best_route_id: str
    ranking: tuple[str, ...]  # route ids, best first
    reason: str
    all_blocked: bool  # every route has some No Travel exposure


def rank_routes(summaries: Sequence[RouteSummary]) -> Recommendation:
    if not summaries:
        raise ValueError("at least one route is required")

    ordered = sorted(summaries, key=_sort_key)  # sorted() is stable: ties keep input order
    best = ordered[0]
    return Recommendation(
        best_route_id=best.route_id,
        ranking=tuple(s.route_id for s in ordered),
        reason=_reason(ordered),
        all_blocked=all(s.no_travel_miles > 0 for s in summaries),
    )


def _sort_key(s: RouteSummary) -> tuple[float, float, float, float, int]:
    return (
        round(s.no_travel_miles, 1),
        round(s.severe_miles, 1),
        round(s.high_miles, 1),
        round(s.avg_risk, 3),
        round(s.duration_s),
    )


def _reason(ordered: Sequence[RouteSummary]) -> str:
    best = ordered[0]
    if len(ordered) == 1:
        return f"{best.label} is the only route available"

    runner_up = ordered[1]
    best_key, other_key = _sort_key(best), _sort_key(runner_up)
    for name, mine, theirs in zip(_KEYS, best_key, other_key, strict=True):
        if mine != theirs:
            return _explain(name, best, runner_up)
    return f"{best.label} and {runner_up.label} are equal on weather risk and travel time"


def _explain(key: str, best: RouteSummary, other: RouteSummary) -> str:
    if key == "no_travel":
        return (
            f"{best.label} has {best.no_travel_miles:.0f} mi of No Travel conditions "
            f"vs {other.no_travel_miles:.0f} mi on {other.label}"
        )
    if key == "severe":
        return (
            f"{best.label} has {best.severe_miles:.0f} mi of Severe weather "
            f"vs {other.severe_miles:.0f} mi on {other.label}"
        )
    if key == "high":
        return (
            f"Severe miles are equal; {best.label} has {best.high_miles:.0f} mi of High "
            f"weather vs {other.high_miles:.0f} mi on {other.label}"
        )
    if key == "avg_risk":
        return (
            f"Severe and High miles are equal; {best.label} has the lower average risk "
            f"({best.avg_risk:.2f} vs {other.avg_risk:.2f})"
        )
    return (
        f"Weather risk is identical; {best.label} is fastest "
        f"({_hours(best.duration_s)} vs {_hours(other.duration_s)})"
    )


def _hours(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"
