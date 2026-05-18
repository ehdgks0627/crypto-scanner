from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any, Mapping


ENGINE_VERSION = "risk-engine-v1"
DEFAULT_WEIGHTS = {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0}

SENSITIVITY_FACTORS = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
EXPOSURE_FACTORS = {"public_internet": 1.0, "dmz": 0.7, "internal_network": 0.4, "air_gapped": 0.1}
CRITICALITY_FACTORS = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
ROLE_SENSITIVITY_FACTORS = {
    "auth": 0.9,
    "pki": 0.9,
    "kms": 0.9,
    "database": 0.8,
    "db": 0.8,
    "postgres": 0.8,
    "postgresql": 0.8,
    "mysql": 0.8,
    "mail": 0.6,
    "smtp": 0.6,
    "imap": 0.6,
    "pop3": 0.6,
}
ROLE_CRITICALITY_FACTORS = {
    "auth": 1.0,
    "pki": 1.0,
    "kms": 1.0,
    "payment": 1.0,
    "database": 0.8,
    "db": 0.8,
    "postgres": 0.8,
    "postgresql": 0.8,
    "mysql": 0.8,
    "mail": 0.6,
    "vpn": 0.6,
    "messaging": 0.6,
    "web-frontend": 0.7,
    "api-gateway": 0.7,
}
PROTOCOL_SENSITIVITY_FACTORS = {"SMTP": 0.6, "IMAP": 0.6, "POP3": 0.6}


@dataclass(frozen=True)
class RiskResult:
    score: int
    tier: str
    factors: dict[str, float]
    weighted_factors: dict[str, float]
    sources: dict[str, str]
    raw: float
    weighted_raw: float
    weights: dict[str, float]
    engine_version: str = ENGINE_VERSION


def compute_risk(
    *,
    algorithm: str | None,
    algorithm_family: str | None,
    asset_type: str | None,
    context: Mapping[str, Any] | None,
    weights: Mapping[str, float] | None = None,
    target_ip: str | None = None,
    protocol_hint: str | None = None,
    context_sources: Mapping[str, str] | None = None,
) -> RiskResult:
    resolved_weights = normalize_weights(weights)
    resolved_context = dict(context or {})
    resolved_sources = dict(context_sources or {})

    factors = {
        "a": algorithm_factor(algorithm, algorithm_family, asset_type),
        "d": data_factor(resolved_context, protocol_hint),
        "e": exposure_factor(resolved_context, target_ip),
        "l": lifespan_factor(resolved_context),
        "c": criticality_factor(resolved_context),
    }
    sources = {
        "a": "algorithm_table",
        "d": resolved_sources.get("sensitivity", "heuristic"),
        "e": resolved_sources.get("exposure", "heuristic"),
        "l": resolved_sources.get("lifespan_years", "heuristic"),
        "c": resolved_sources.get("criticality", "heuristic"),
    }
    raw = factors["a"] * average_context_factor(factors)
    weighted_factors = {
        "a": apply_factor_weight(factors["a"], resolved_weights["wA"]),
        "d": apply_factor_weight(factors["d"], resolved_weights["wD"]),
        "e": apply_factor_weight(factors["e"], resolved_weights["wE"]),
        "l": apply_factor_weight(factors["l"], resolved_weights["wL"]),
        "c": apply_factor_weight(factors["c"], resolved_weights["wC"]),
    }
    weighted_raw = weighted_factors["a"] * average_context_factor(weighted_factors)
    score = max(0, min(100, round(weighted_raw * 100)))
    return RiskResult(
        score=score,
        tier=tier_for_score(score),
        factors=factors,
        weighted_factors=weighted_factors,
        sources=sources,
        raw=raw,
        weighted_raw=weighted_raw,
        weights=resolved_weights,
    )


def normalize_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    source = {**DEFAULT_WEIGHTS, **dict(weights or {})}
    normalized = {}
    for key in DEFAULT_WEIGHTS:
        value = float(source[key])
        if value < 0.5 or value > 2.0:
            raise ValueError(f"{key} must be between 0.5 and 2.0")
        normalized[key] = value
    return normalized


def tier_for_score(score: int | float) -> str:
    rounded = round(score)
    if rounded >= 80:
        return "CRITICAL"
    if rounded >= 60:
        return "HIGH"
    if rounded >= 30:
        return "MEDIUM"
    return "LOW"


def average_context_factor(factors: Mapping[str, float]) -> float:
    return (factors["d"] + factors["e"] + factors["l"] + factors["c"]) / 4


def apply_factor_weight(value: float, weight: float) -> float:
    if value <= 0:
        return 0.0
    if value >= 1:
        return 1.0
    weighted = 0.5 + ((value - 0.5) * weight)
    return max(0.0, min(1.0, weighted))


def algorithm_factor(algorithm: str | None, algorithm_family: str | None, asset_type: str | None = None) -> float:
    name = normalize_algorithm_text(algorithm)
    family = normalize_algorithm_text(algorithm_family)
    combined = f"{family} {name}".strip()

    if not combined:
        return 0.5
    if "ML-KEM" in combined or "ML-DSA" in combined or "SLH-DSA" in combined or "FALCON" in combined or "FN-DSA" in combined:
        if "+" in combined or "HYBRID" in combined:
            return 0.1
        return 0.0
    if "HYBRID" in combined:
        return 0.1
    if "RSA" in combined:
        return sized_factor(name, default=0.95, thresholds=[(1024, 1.0), (2048, 0.95), (3072, 0.9), (4096, 0.85)])
    if "DSA" in combined and "ECDSA" not in combined:
        return sized_factor(name, default=0.95, thresholds=[(1024, 1.0), (2048, 0.95), (3072, 0.9), (4096, 0.85)])
    if "ECDSA" in combined or "ECDH" in combined:
        if "P-256" in combined or "SECP256" in combined:
            return 0.95
        if "P-384" in combined or "SECP384" in combined:
            return 0.9
        if "P-521" in combined or "SECP521" in combined:
            return 0.85
        return 0.9
    if "X25519" in combined or "X448" in combined or "ED25519" in combined or "ED448" in combined:
        return 0.9
    if "DH" in combined or "MODP" in combined:
        return sized_factor(name, default=0.95, thresholds=[(1024, 1.0), (2048, 0.95), (3072, 0.9), (4096, 0.85)])
    if "SHA-1" in combined or "SHA1" in combined:
        return 1.0 if "SIGN" in combined or asset_type in {"certificate", "signature"} else 0.5
    if "SHA-256" in combined or "SHA-384" in combined or "SHA-512" in combined or "SHA2" in combined:
        return 0.05
    if "AES-128" in combined:
        return 0.1
    if "AES-192" in combined or "AES-256" in combined:
        return 0.05
    if "CHACHA20" in combined or "HMAC" in combined:
        return 0.05
    return 0.5


def sized_factor(name: str, *, default: float, thresholds: list[tuple[int, float]]) -> float:
    for size, factor in thresholds:
        if str(size) in name:
            return factor
    return default


def data_factor(context: Mapping[str, Any], protocol_hint: str | None = None) -> float:
    explicit = normalized_context_value(context.get("sensitivity"))
    if explicit in SENSITIVITY_FACTORS:
        return SENSITIVITY_FACTORS[explicit]
    role = normalized_context_value(context.get("service_role"))
    if role in ROLE_SENSITIVITY_FACTORS:
        return ROLE_SENSITIVITY_FACTORS[role]
    protocol = (protocol_hint or "").upper()
    return PROTOCOL_SENSITIVITY_FACTORS.get(protocol, 0.5)


def exposure_factor(context: Mapping[str, Any], target_ip: str | None = None) -> float:
    explicit = normalized_context_value(context.get("exposure"))
    if explicit in EXPOSURE_FACTORS:
        return EXPOSURE_FACTORS[explicit]
    if target_ip:
        try:
            parsed = ip_address(target_ip)
        except ValueError:
            return 0.5
        if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
            return EXPOSURE_FACTORS["internal_network"]
        return EXPOSURE_FACTORS["public_internet"]
    return 0.5


def lifespan_factor(context: Mapping[str, Any]) -> float:
    value = context.get("lifespan_years")
    if value is None:
        return 0.5
    years = float(value)
    if years >= 25:
        return 1.0
    if years >= 15:
        return 0.85
    if years >= 10:
        return 0.7
    if years >= 5:
        return 0.5
    if years >= 1:
        return 0.3
    return 0.1


def criticality_factor(context: Mapping[str, Any]) -> float:
    explicit = normalized_context_value(context.get("criticality"))
    if explicit in CRITICALITY_FACTORS:
        return CRITICALITY_FACTORS[explicit]
    role = normalized_context_value(context.get("service_role"))
    return ROLE_CRITICALITY_FACTORS.get(role, 0.5)


def normalize_algorithm_text(value: str | None) -> str:
    return (value or "").strip().upper()


def normalized_context_value(value: Any) -> str:
    return str(value or "").strip().lower()
