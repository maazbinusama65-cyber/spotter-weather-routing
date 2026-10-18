"""Combine checkpoints and weather into per-route totals used for ranking and display."""

from collections.abc import Sequence
from dataclasses import dataclass

from .risk import CheckpointRisk, RiskLevel, WeatherSample, classify_checkpoint
from .sampling import Checkpoint


@dataclass(frozen=True)
class CheckpointAnalysis:
    checkpoint: Checkpoint
    weather: WeatherSample | None  # None when the forecast could not be fetched
    risk: CheckpointRisk | None


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    label: str
    distance_mi: float
    duration_s: float
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    unknown_miles: float
    avg_risk: float  # mile-weighted mean of risk level (0-4) over miles with known weather
    max_level: RiskLevel


def evaluate_checkpoints(
    checkpoints: Sequence[Checkpoint],
    samples: Sequence[WeatherSample | None],
    load_lb: float,
) -> tuple[CheckpointAnalysis, ...]:
    if len(samples) != len(checkpoints):
        raise ValueError(
            f"expected one weather sample per checkpoint ({len(checkpoints)}), got {len(samples)}"
        )
    return tuple(
        CheckpointAnalysis(
            checkpoint=checkpoint,
            weather=sample,
            risk=None if sample is None else classify_checkpoint(sample, load_lb),
        )
        for checkpoint, sample in zip(checkpoints, samples, strict=True)
    )


def summarize_route(
    route_id: str,
    label: str,
    duration_s: float,
    analyses: Sequence[CheckpointAnalysis],
) -> RouteSummary:
    miles = {level: 0.0 for level in RiskLevel}
    unknown = 0.0
    weighted_risk = 0.0
    max_level = RiskLevel.LOW

    for analysis in analyses:
        owned = analysis.checkpoint.segment_miles
        if analysis.risk is None:
            unknown += owned
            continue
        level = analysis.risk.level
        miles[level] += owned
        weighted_risk += int(level) * owned
        max_level = max(max_level, level)

    known = sum(miles.values())
    return RouteSummary(
        route_id=route_id,
        label=label,
        distance_mi=known + unknown,
        duration_s=duration_s,
        no_travel_miles=miles[RiskLevel.NO_TRAVEL],
        severe_miles=miles[RiskLevel.SEVERE],
        high_miles=miles[RiskLevel.HIGH],
        moderate_miles=miles[RiskLevel.MODERATE],
        low_miles=miles[RiskLevel.LOW],
        unknown_miles=unknown,
        avg_risk=weighted_risk / known if known else 0.0,
        max_level=max_level,
    )
