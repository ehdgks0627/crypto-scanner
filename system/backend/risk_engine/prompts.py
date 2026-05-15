from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


QUALITATIVE_RISK_PROMPT_VERSION = "qualitative-risk-v1"

QUALITATIVE_RISK_SYSTEM_PROMPT = """You are a PQC migration risk analyst.
Assess one cryptographic asset for quantum-era migration planning.
Use only the supplied asset, context, source, and risk data.
Return concise JSON that matches the requested schema."""

QUALITATIVE_RISK_RESPONSE_SCHEMA = {
    "summary": "Short operational risk summary.",
    "threat_scenarios": ["harvest_now_decrypt_later", "network_exposed_cryptographic_service"],
    "migration_recommendation": "Actionable PQC or hybrid migration recommendation.",
    "confidence": 0.0,
}


def build_qualitative_risk_prompt(
    *,
    asset: Mapping[str, Any],
    context: Mapping[str, Any],
    context_sources: Mapping[str, str],
    risk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "asset": _json_safe(asset),
        "context": _json_safe(context),
        "context_sources": _json_safe(context_sources),
        "risk": _json_safe(risk or {}),
    }
    user_prompt = (
        "Evaluate this cryptographic asset for PQC migration priority.\n"
        "Focus on HNDL exposure, service criticality, communication exposure, and migration urgency.\n"
        "Do not invent facts not present in the payload.\n\n"
        f"Payload:\n{json.dumps(payload, sort_keys=True, indent=2)}\n\n"
        f"Required JSON schema:\n{json.dumps(QUALITATIVE_RISK_RESPONSE_SCHEMA, sort_keys=True, indent=2)}"
    )
    return {
        "version": QUALITATIVE_RISK_PROMPT_VERSION,
        "system": QUALITATIVE_RISK_SYSTEM_PROMPT,
        "user": user_prompt,
        "response_schema": QUALITATIVE_RISK_RESPONSE_SCHEMA,
        "payload": payload,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(inner) for inner in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
