from __future__ import annotations

from typing import Any, Iterable, Mapping


QUANTUM_VULNERABLE_FAMILIES = {"RSA", "DSA", "ECDSA", "ECDH", "DH", "ED25519", "ED448", "X25519", "X448"}
PQC_MARKERS = ("ML-KEM", "ML-DSA", "SLH-DSA", "FALCON", "FN-DSA")
AGILITY_CAPABILITIES = {
    "config_policy": 20,
    "automated_rotation": 20,
    "rollback_supported": 20,
    "rescan_validation": 15,
    "owner_known": 10,
    "canary_supported": 10,
    "inventory_fresh": 5,
}


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
    recommendation = build_recommendation(current_algorithm, algorithm_family, asset_type, context, capability_set)
    agility = build_agility(capability_set, recommendation["blockers"])
    return {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "asset_type": asset_type,
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


def build_recommendation(algorithm: str, algorithm_family: str | None, asset_type: str, context: Mapping[str, Any], capabilities: set[str]) -> dict:
    candidate = candidate_for_algorithm(algorithm, algorithm_family, asset_type)
    strategy = choose_strategy(candidate, context)
    target_set = candidate["hybrid_set"] if strategy == "hybrid" else candidate["replace_set"]
    final_set = candidate["replace_set"] or target_set
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
    if any(marker in combined for marker in PQC_MARKERS):
        return {"kind": "pqc", "hybrid_set": [algorithm], "replace_set": [algorithm], "classically_weak": False}
    if "SHA-1" in combined or "SHA1" in combined:
        return {"kind": "hash", "hybrid_set": [], "replace_set": ["SHA-256+"], "classically_weak": True}
    if "AES-128" in combined:
        return {"kind": "symmetric", "hybrid_set": [], "replace_set": ["AES-256"], "classically_weak": False}
    if "AES-192" in combined or "AES-256" in combined or "CHACHA20" in combined or "HMAC" in combined:
        return {"kind": "safe_classical", "hybrid_set": [algorithm], "replace_set": [algorithm], "classically_weak": False}
    if "ECDSA" in combined:
        target = "ML-DSA-87" if "384" in combined or "521" in combined else "ML-DSA-65"
        curve = "ECDSA P-384" if target == "ML-DSA-87" else "ECDSA P-256"
        return {"kind": "signature", "hybrid_set": [curve, target], "replace_set": [target], "classically_weak": False}
    if "ED25519" in combined or "ED448" in combined:
        return {"kind": "signature", "hybrid_set": [algorithm, "ML-DSA-65"], "replace_set": ["ML-DSA-65"], "classically_weak": False}
    if "ECDH" in combined or "X25519" in combined or "X448" in combined:
        kem = "ML-KEM-1024" if "384" in combined or "521" in combined or "X448" in combined else "ML-KEM-768"
        classical = "X448" if kem == "ML-KEM-1024" else "X25519"
        return {"kind": "kem", "hybrid_set": [classical, kem], "replace_set": [kem], "classically_weak": False}
    if "DH" in combined:
        return {"kind": "kem", "hybrid_set": ["X25519", "ML-KEM-768"], "replace_set": ["ML-KEM-768"], "classically_weak": "1024" in combined}
    if "RSA" in combined:
        if asset_type in {"key", "protocol"}:
            return {"kind": "kem", "hybrid_set": ["X25519", "ML-KEM-768"], "replace_set": ["ML-KEM-768"], "classically_weak": "1024" in combined}
        return {"kind": "signature", "hybrid_set": ["RSA-2048", "ML-DSA-65"], "replace_set": ["ML-DSA-65"], "classically_weak": "1024" in combined}
    return {"kind": "unknown", "hybrid_set": [algorithm], "replace_set": [algorithm], "classically_weak": False}


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
                "kind": "enable_hybrid",
                "title": "Enable hybrid transition",
                "action": f"Deploy {recommendation['target_algorithm']} while retaining the classical fallback.",
                "validation": "; ".join(recommendation["validation"]),
            }
        )
        order += 1
        steps.append(
            {
                "order": order,
                "kind": "remove_classical_fallback",
                "title": "Remove classical fallback",
                "action": f"After compatibility is proven, converge on {', '.join(recommendation['final_algorithm_set'])}.",
                "validation": "Rescan and verify the classical-only algorithm is no longer negotiated.",
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
    return [
        {
            "strategy": "replace",
            "target_algorithm": " + ".join(recommendation["final_algorithm_set"]),
            "trade_off": "Removes the classical dependency earlier but requires stronger compatibility validation.",
        }
    ]


def rollback_for(strategy: str, algorithm: str) -> str:
    if strategy == "no_change":
        return "No rollout is required; preserve the current configuration."
    if strategy == "hybrid":
        return f"Keep the existing {algorithm} path enabled until hybrid compatibility is verified."
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
        return f"{algorithm} should be replaced with {target_algorithm} because the current primitive is weak or has a direct safer successor."
    details = []
    if context.get("lifespan_years") is not None:
        details.append(f"lifespan={context['lifespan_years']}y")
    if context.get("criticality"):
        details.append(f"criticality={context['criticality']}")
    if context.get("exposure"):
        details.append(f"exposure={context['exposure']}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"{algorithm} is quantum-vulnerable; use {target_algorithm} as a hybrid transition before converging to the final PQC set{suffix}."


def confidence_for(strategy: str, blockers: list[str]) -> float:
    base = 0.9 if strategy == "no_change" else 0.82
    return round(max(0.45, base - len(blockers) * 0.05), 2)


def is_quantum_vulnerable(algorithm: str, algorithm_family: str | None) -> bool:
    combined = f"{normalize(algorithm_family)} {normalize(algorithm)}"
    if any(marker in combined for marker in PQC_MARKERS):
        return False
    return any(family in combined for family in QUANTUM_VULNERABLE_FAMILIES)


def infer_key_size(algorithm: str) -> int | None:
    for size in (1024, 2048, 3072, 4096, 256, 384, 521, 768):
        if str(size) in algorithm:
            return size
    return None


def normalize(value: str | None) -> str:
    return (value or "").upper().strip()
