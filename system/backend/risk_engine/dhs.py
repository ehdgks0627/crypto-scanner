from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DHS_RISK_ENGINE_VERSION = "dhs-risk-v1"

DHS_CRITERION_WEIGHTS = {
    "asset_value": 1.0,
    "protected_information": 1.1,
    "communication_scope": 1.0,
    "sharing_level": 0.8,
    "critical_infrastructure": 1.2,
    "protection_duration": 1.6,
}

RATING_SCORES = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}


@dataclass(frozen=True)
class DhsRiskResult:
    score_10: float
    priority: str
    weighted_raw: float
    weights: dict[str, float]
    criteria: dict[str, dict[str, float]]
    missing_criteria: list[str]
    engine_version: str = DHS_RISK_ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "score_10": self.score_10,
            "priority": self.priority,
            "weighted_raw": self.weighted_raw,
            "weights": self.weights,
            "criteria": self.criteria,
            "missing_criteria": self.missing_criteria,
            "engine_version": self.engine_version,
        }


def compute_dhs_risk(dhs_criteria: Mapping[str, Any] | None) -> DhsRiskResult:
    source = dict(dhs_criteria or {})
    denominator = sum(DHS_CRITERION_WEIGHTS.values())
    weighted_total = 0.0
    criteria = {}
    missing = []

    for name, weight in DHS_CRITERION_WEIGHTS.items():
        value = source.get(name)
        if not isinstance(value, Mapping):
            missing.append(name)
            criteria[name] = {"score": 0.0, "weight": weight, "weighted_score": 0.0}
            continue
        score = _criterion_score(value)
        weighted_score = round(score * weight, 4)
        weighted_total += weighted_score
        criteria[name] = {
            "score": score,
            "weight": weight,
            "weighted_score": weighted_score,
        }

    weighted_raw = round(weighted_total / denominator, 4) if denominator else 0.0
    score_10 = round(weighted_raw * 10, 1)
    return DhsRiskResult(
        score_10=score_10,
        priority=priority_for_dhs_score(score_10),
        weighted_raw=weighted_raw,
        weights=dict(DHS_CRITERION_WEIGHTS),
        criteria=criteria,
        missing_criteria=missing,
    )


def priority_for_dhs_score(score_10: int | float) -> str:
    score = float(score_10)
    if score >= 8:
        return "P1"
    if score >= 5:
        return "P2"
    return "P3"


def _criterion_score(value: Mapping[str, Any]) -> float:
    explicit_score = value.get("score")
    if explicit_score is not None:
        try:
            parsed = float(explicit_score)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            if parsed > 1 and parsed <= 100:
                parsed = parsed / 100
            return round(max(0.0, min(1.0, parsed)), 4)

    rating = str(value.get("rating") or "").strip().lower()
    return RATING_SCORES.get(rating, 0.0)
