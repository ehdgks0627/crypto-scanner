from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping


MAPPING_RULES_PATH = Path(__file__).with_name("mapping_rules.json")
AGILITY_CAPABILITIES = {
    "config_policy": 20,
    "automated_rotation": 20,
    "rollback_supported": 20,
    "rescan_validation": 15,
    "owner_known": 10,
    "canary_supported": 10,
    "inventory_fresh": 5,
}
LONG_TERM_SIGNATURE_MARKERS = (
    "archive",
    "audit",
    "backup",
    "code_signing",
    "codesign",
    "legal",
    "notary",
    "package",
    "records",
    "timestamp",
    "tsa",
)


def recommend_migration(
    *,
    asset_id: int,
    asset_name: str,
    asset_type: str,
    algorithm: str | None,
    algorithm_family: str | None,
    risk_score: int,
    tier: str,
    context: Mapping[str, Any] | None = None,
    capabilities: Iterable[str] | None = None,
) -> dict:
    context = dict(context or {})
    capability_set = set(capabilities or [])
    current_algorithm = algorithm or algorithm_family or "Unknown"
    candidate = specialize_candidate_for_context(candidate_for_algorithm(current_algorithm, algorithm_family, asset_type), context)
    recommendation = build_recommendation(current_algorithm, algorithm_family, asset_type, context, capability_set, candidate)
    agility = build_agility(capability_set, recommendation["blockers"])
    return {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "asset_type": asset_type,
        "asset_purpose": candidate["purpose"],
        "current": {
            "algorithm": current_algorithm,
            "key_size_bits": infer_key_size(current_algorithm),
            "quantum_vulnerable": is_quantum_vulnerable(current_algorithm, algorithm_family),
        },
        "recommendation": recommendation,
        "alternatives": build_alternatives(recommendation),
        "risk_score": round(risk_score),
        "tier": tier,
        "agility": agility,
        "playbook": build_playbook(recommendation, agility),
    }


def build_recommendation(
    algorithm: str,
    algorithm_family: str | None,
    asset_type: str,
    context: Mapping[str, Any],
    capabilities: set[str],
    candidate: Mapping[str, Any] | None = None,
) -> dict:
    candidate = candidate or candidate_for_algorithm(algorithm, algorithm_family, asset_type)
    strategy = choose_strategy(candidate, context)
    final_set = candidate["replace_set"] or candidate["hybrid_set"]
    target_set = final_set if strategy == "hybrid" else candidate["replace_set"]
    blockers = build_blockers(strategy, capabilities, candidate)
    phase = {"hybrid": "hybrid_first", "replace": "replace_now", "no_change": "monitor"}[strategy]
    target_algorithm = " + ".join(target_set) if target_set else algorithm
    return {
        "strategy": strategy,
        "target_algorithm": target_algorithm,
        "target_algorithm_set": target_set or [algorithm],
        "final_algorithm_set": final_set or target_set or [algorithm],
        "phase": phase,
        "blockers": blockers,
        "rollback": rollback_for(strategy, algorithm),
        "validation": validation_for(strategy, asset_type),
        "rationale": rationale_for(strategy, algorithm, target_algorithm, context, candidate),
        "confidence": confidence_for(strategy, blockers),
    }


def candidate_for_algorithm(algorithm: str, algorithm_family: str | None, asset_type: str) -> dict:
    text = normalize(algorithm)
    family = normalize(algorithm_family)
    combined = f"{family} {text}".strip()
    for rule in mapping_rules():
        if not _rule_matches(rule, combined, asset_type):
            continue
        return _candidate_from_rule(rule, algorithm, combined)
    return {"kind": "unknown", "purpose": "unknown", "hybrid_set": [algorithm], "replace_set": [algorithm], "classically_weak": False}


def specialize_candidate_for_context(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> dict:
    if not _is_long_term_signature_context(candidate, context):
        return dict(candidate)
    specialized = dict(candidate)
    specialized["purpose"] = "long_term_signature"
    specialized["hybrid_set"] = list(specialized.get("long_term_hybrid_set") or specialized["hybrid_set"])
    specialized["replace_set"] = list(specialized.get("long_term_replace_set") or specialized["replace_set"])
    return specialized


def choose_strategy(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    if candidate["kind"] in {"pqc", "safe_classical"}:
        return "no_change"
    if candidate["kind"] in {"hash", "symmetric"} or candidate["classically_weak"]:
        return "replace"
    if candidate["kind"] == "unknown":
        return "hybrid"
    if (context.get("lifespan_years") or 0) >= 10:
        return "hybrid"
    if context.get("exposure") == "public_internet" and context.get("criticality") in {"high", "critical"}:
        return "hybrid"
    if context.get("service_role") in {"pki", "auth", "kms", "payment"}:
        return "hybrid"
    return "hybrid"


def build_blockers(strategy: str, capabilities: set[str], candidate: Mapping[str, Any]) -> list[str]:
    blockers = []
    if strategy in {"hybrid", "replace"} and "runtime_pqc_supported" not in capabilities:
        blockers.append("runtime_capability_unknown")
    if strategy in {"hybrid", "replace"} and "config_policy" not in capabilities:
        blockers.append("config_policy_missing")
    if strategy in {"hybrid", "replace"} and "rescan_validation" not in capabilities:
        blockers.append("validation_probe_missing")
    if strategy != "no_change" and "rollback_supported" not in capabilities:
        blockers.append("rollback_undefined")
    if candidate["kind"] == "unknown":
        blockers.append("algorithm_classification_unknown")
    return blockers


def build_agility(capabilities: set[str], recommendation_blockers: list[str]) -> dict:
    score = min(100, sum(AGILITY_CAPABILITIES.get(capability, 0) for capability in capabilities))
    score = max(0, score - min(len(recommendation_blockers) * 8, 40))
    if score >= 75:
        level = "HIGH"
    elif score >= 45:
        level = "MEDIUM"
    else:
        level = "LOW"
    return {
        "score": score,
        "level": level,
        "blockers": recommendation_blockers,
        "enablers": sorted(capability for capability in capabilities if capability in AGILITY_CAPABILITIES),
    }


def build_playbook(recommendation: Mapping[str, Any], agility: Mapping[str, Any]) -> list[dict]:
    if recommendation["strategy"] == "no_change":
        return [
            {
                "order": 1,
                "kind": "monitor",
                "title": "Monitor cryptographic posture",
                "action": "Keep the current algorithm and rescan after runtime or policy changes.",
                "validation": "Confirm the asset remains present with the same PQC-safe algorithm.",
            }
        ]
    steps = []
    order = 1
    if agility["blockers"]:
        steps.append(
            {
                "order": order,
                "kind": "remove_blockers",
                "title": "Resolve agility blockers",
                "action": f"Address blockers before rollout: {', '.join(agility['blockers'])}.",
                "validation": "Repeat discovery and confirm capabilities are known.",
            }
        )
        order += 1
    if recommendation["strategy"] == "hybrid":
        steps.append(
            {
                "order": order,
                "kind": "prepare_pqc_transition",
                "title": "Prepare PQC transition",
                "action": f"Introduce {recommendation['target_algorithm']} and validate service compatibility.",
                "validation": "; ".join(recommendation["validation"]),
            }
        )
        order += 1
        steps.append(
            {
                "order": order,
                "kind": "complete_pqc_transition",
                "title": "Complete PQC transition",
                "action": f"After compatibility is proven, converge on {', '.join(recommendation['final_algorithm_set'])}.",
                "validation": "Rescan and verify the PQC target is active.",
            }
        )
        return steps
    steps.append(
        {
            "order": order,
            "kind": "replace_algorithm",
            "title": "Replace algorithm",
            "action": f"Replace the current algorithm with {recommendation['target_algorithm']}.",
            "validation": "; ".join(recommendation["validation"]),
        }
    )
    return steps


def build_alternatives(recommendation: Mapping[str, Any]) -> list[dict]:
    if recommendation["strategy"] != "hybrid":
        return []
    final_algorithm = " + ".join(recommendation["final_algorithm_set"])
    if final_algorithm == recommendation["target_algorithm"]:
        return []
    return [
        {
            "strategy": "replace",
            "target_algorithm": final_algorithm,
            "trade_off": "Removes the classical dependency earlier but requires stronger compatibility validation.",
        }
    ]


def rollback_for(strategy: str, algorithm: str) -> str:
    if strategy == "no_change":
        return "No rollout is required; preserve the current configuration."
    if strategy == "hybrid":
        return "Keep an approved rollback path available until service compatibility is verified."
    return f"Keep a signed and deployable copy of the previous {algorithm} configuration for rollback."


def validation_for(strategy: str, asset_type: str) -> list[str]:
    if strategy == "no_change":
        return ["periodic_rescan"]
    checks = ["rescan_crypto_inventory", "verify_client_compatibility"]
    if asset_type == "certificate":
        checks.append("validate_certificate_chain")
    if asset_type in {"protocol", "key"}:
        checks.append("verify_negotiated_algorithm")
    return checks


def rationale_for(strategy: str, algorithm: str, target_algorithm: str, context: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    if strategy == "no_change":
        return f"{algorithm} is already PQC-safe or does not require immediate migration under the current policy."
    if strategy == "replace":
        return f"The current primitive should be replaced with {target_algorithm} because a direct safer successor is available."
    if candidate.get("purpose") == "long_term_signature":
        return f"Long-term signature use requires a PQC target; prioritize {target_algorithm} for durable signature protection."
    details = []
    if context.get("lifespan_years") is not None:
        details.append(f"lifespan={context['lifespan_years']}y")
    if context.get("criticality"):
        details.append(f"criticality={context['criticality']}")
    if context.get("exposure"):
        details.append(f"exposure={context['exposure']}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"The current public-key primitive is quantum-vulnerable; prioritize {target_algorithm} as the PQC target{suffix}."


def confidence_for(strategy: str, blockers: list[str]) -> float:
    base = 0.9 if strategy == "no_change" else 0.82
    return round(max(0.45, base - len(blockers) * 0.05), 2)


def is_quantum_vulnerable(algorithm: str, algorithm_family: str | None) -> bool:
    combined = f"{normalize(algorithm_family)} {normalize(algorithm)}"
    if any(marker in combined for marker in pqc_markers()):
        return False
    return any(marker in combined for marker in quantum_vulnerable_markers())


def infer_key_size(algorithm: str) -> int | None:
    for size in (1024, 2048, 3072, 4096, 256, 384, 521, 768):
        if str(size) in algorithm:
            return size
    return None


def normalize(value: object | None) -> str:
    return str(value or "").upper().strip()


@lru_cache
def mapping_config() -> dict[str, Any]:
    with MAPPING_RULES_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    return data


def mapping_rules() -> list[Mapping[str, Any]]:
    return list(mapping_config().get("rules") or [])


def pqc_markers() -> tuple[str, ...]:
    return tuple(normalize(marker) for marker in mapping_config().get("pqc_markers", []))


def quantum_vulnerable_markers() -> tuple[str, ...]:
    return tuple(normalize(marker) for marker in mapping_config().get("quantum_vulnerable_markers", []))


def _rule_matches(rule: Mapping[str, Any], combined: str, asset_type: str | None) -> bool:
    asset_types = rule.get("asset_types")
    if asset_types and asset_type not in set(asset_types):
        return False
    pattern = rule.get("match_regex")
    if not pattern:
        return False
    return re.search(str(pattern), combined) is not None


def _candidate_from_rule(rule: Mapping[str, Any], algorithm: str, combined: str) -> dict:
    if rule.get("preserve_current"):
        hybrid_set = [algorithm]
        replace_set = [algorithm]
    else:
        hybrid_set = _render_algorithm_set(rule.get("hybrid_set", []), algorithm)
        replace_set = _render_algorithm_set(rule.get("replace_set", []), algorithm)
    weak_markers = [normalize(value) for value in rule.get("classically_weak_if_contains", [])]
    candidate = {
        "kind": str(rule.get("kind", "unknown")),
        "purpose": str(rule.get("purpose") or _infer_purpose(rule, combined)),
        "hybrid_set": hybrid_set,
        "replace_set": replace_set,
        "classically_weak": bool(rule.get("classically_weak")) or any(marker in combined for marker in weak_markers),
    }
    if "long_term_hybrid_set" in rule:
        candidate["long_term_hybrid_set"] = _render_algorithm_set(rule.get("long_term_hybrid_set", []), algorithm)
    if "long_term_replace_set" in rule:
        candidate["long_term_replace_set"] = _render_algorithm_set(rule.get("long_term_replace_set", []), algorithm)
    return candidate


def _render_algorithm_set(values: Iterable[str], algorithm: str) -> list[str]:
    return [str(value).replace("{algorithm}", algorithm) for value in values]


def _infer_purpose(rule: Mapping[str, Any], combined: str) -> str:
    kind = str(rule.get("kind", "unknown"))
    if "SLH-DSA" in combined:
        return "long_term_signature"
    if any(marker in combined for marker in ("ML-DSA", "FALCON", "FN-DSA")):
        return "digital_signature"
    if "ML-KEM" in combined:
        return "key_exchange"
    if kind == "signature":
        return "digital_signature"
    if kind == "kem":
        return "key_exchange"
    if kind == "hash":
        return "hash_integrity"
    if kind == "symmetric":
        return "symmetric_encryption"
    if kind == "safe_classical":
        if any(marker in combined for marker in ("AES", "CHACHA")):
            return "symmetric_encryption"
        if any(marker in combined for marker in ("SHA", "HMAC")):
            return "hash_integrity"
    return "unknown"


def _is_long_term_signature_context(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    if candidate.get("kind") != "signature":
        return False
    if not candidate.get("long_term_replace_set"):
        return False
    if context.get("long_term_signature") is True:
        return True
    profile = normalize(context.get("signature_profile")).replace("-", "_")
    if profile in {"LONG_TERM", "LONG_TERM_SIGNATURE", "ARCHIVE", "ARCHIVAL"}:
        return True
    role = normalize(context.get("service_role")).replace("-", "_")
    purpose = normalize(context.get("purpose")).replace("-", "_")
    combined = f"{role} {purpose}"
    return any(marker.upper() in combined for marker in LONG_TERM_SIGNATURE_MARKERS)
