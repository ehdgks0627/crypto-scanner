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


class QualitativeRiskResponseParseError(ValueError):
    pass


def build_qualitative_risk_prompt(
    *,
    asset: Mapping[str, Any],
    context: Mapping[str, Any],
    context_sources: Mapping[str, str],
    operational_context: Mapping[str, Any] | None = None,
    risk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "asset": _json_safe(asset),
        "context": _json_safe(context),
        "context_sources": _json_safe(context_sources),
        "operational_context": _json_safe(operational_context or {}),
        "risk": _json_safe(risk or {}),
    }
    user_prompt = (
        "Evaluate this cryptographic asset for PQC migration priority.\n"
        "Focus on HNDL exposure, service criticality, communication exposure, file/config evidence, and migration urgency.\n"
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


def parse_qualitative_risk_response(text: str) -> dict[str, Any]:
    data = _extract_json_object(text)
    return {
        "summary": _required_string(data, "summary"),
        "threat_scenarios": _string_list(data.get("threat_scenarios")),
        "migration_recommendation": _required_string(data, "migration_recommendation"),
        "confidence": _confidence(data.get("confidence")),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(inner) for inner in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _extract_json_object(text: str) -> Mapping[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping):
            return value
    raise QualitativeRiskResponseParseError("LLM response does not contain a JSON object")


def _required_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QualitativeRiskResponseParseError(f"LLM response field '{key}' must be a non-empty string")
    return value.strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list | tuple | set):
        items = list(value)
    else:
        raise QualitativeRiskResponseParseError("LLM response field 'threat_scenarios' must be a string list")
    result = [str(item).strip() for item in items if str(item).strip()]
    if not result:
        raise QualitativeRiskResponseParseError("LLM response field 'threat_scenarios' must not be empty")
    return result


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise QualitativeRiskResponseParseError("LLM response field 'confidence' must be numeric") from exc
    if confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    return round(max(0, min(1, confidence)), 2)
