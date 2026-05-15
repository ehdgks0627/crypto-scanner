from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


QUALITATIVE_RISK_PROMPT_VERSION = "qualitative-risk-v7"

QUALITATIVE_RISK_SYSTEM_PROMPT = """You are a PQC migration risk analyst.
Assess one cryptographic asset for quantum-era migration planning.
Use only the supplied asset, context, source, and risk data.
Return concise JSON that matches the requested schema."""

QUALITATIVE_RISK_RESPONSE_SCHEMA = {
    "summary": "Short operational risk summary.",
    "threat_scenarios": ["harvest_now_decrypt_later", "network_exposed_cryptographic_service"],
    "migration_recommendation": "Actionable PQC or hybrid migration recommendation.",
    "dhs_criteria": {
        "asset_value": {
            "question": "Q1: asset value based on external exposure and business importance.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["public_internet", "critical service role"],
        },
        "protected_information": {
            "question": "Q2: protected information based on data classification and confidentiality needs.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "data_classification": "low|medium|high|critical|unknown",
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["sensitivity:critical", "lifespan_years:10"],
        },
        "communication_scope": {
            "question": "Q3: communication scope based on internal-only versus external bidirectional exposure.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "exposure": "air_gapped|internal_network|dmz|public_internet|unknown",
            "direction": "none|internal_only|external_inbound|external_bidirectional|unknown",
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["exposure:public_internet", "direction:external_bidirectional"],
        },
        "sharing_level": {
            "question": "Q4: sharing level based on third-party or partner integration.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "sharing_scope": "none|internal_only|partner|third_party|public|unknown",
            "external_parties": ["partner_idp", "public_clients"],
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["service_role:api-gateway", "exposure:public_internet"],
        },
        "critical_infrastructure": {
            "question": "Q5: critical infrastructure dependency based on DB, identity, payment, KMS, or gateway role.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "dependency_level": "none|supporting|core|critical|unknown",
            "infrastructure_roles": ["identity_auth", "data_store", "payment", "key_management"],
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["service_role:auth", "dependency_count:2"],
        },
        "protection_duration": {
            "question": "Q6: protection duration based on retention period and HNDL exposure.",
            "rating": "low|medium|high|critical",
            "score": 0.0,
            "lifespan_years": 10,
            "hndl_exposure": "low|medium|high|critical|unknown",
            "rationale": "One-sentence evidence-based explanation.",
            "signals": ["lifespan_years:10", "quantum_vulnerable:true"],
        }
    },
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
        "For DHS Q1 asset_value, rate the asset by external exposure and business importance only.\n"
        "For DHS Q2 protected_information, rate the information protected by the asset using data classification and confidentiality needs.\n"
        "For DHS Q3 communication_scope, rate internal-only versus external bidirectional communication exposure.\n"
        "For DHS Q4 sharing_level, rate third-party, partner, or public sharing paths.\n"
        "For DHS Q5 critical_infrastructure, rate dependency on DB, identity, payment, KMS, gateway, or other core services.\n"
        "For DHS Q6 protection_duration, rate retention duration and HNDL exposure for long-lived protected data.\n"
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
        "dhs_criteria": _dhs_criteria(data.get("dhs_criteria")),
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


def _dhs_criteria(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria' must be an object")
    return {
        "asset_value": _dhs_asset_value(value.get("asset_value")),
        "protected_information": _dhs_protected_information(value.get("protected_information")),
        "communication_scope": _dhs_communication_scope(value.get("communication_scope")),
        "sharing_level": _dhs_sharing_level(value.get("sharing_level")),
        "critical_infrastructure": _dhs_critical_infrastructure(value.get("critical_infrastructure")),
        "protection_duration": _dhs_protection_duration(value.get("protection_duration")),
    }


def _dhs_asset_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.asset_value' must be an object")
    rating = _required_string(value, "rating").lower()
    if rating not in {"low", "medium", "high", "critical"}:
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.asset_value.rating' has an invalid value")
    return {
        "question": str(value.get("question") or "Q1: asset value based on external exposure and business importance."),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _dhs_protected_information(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.protected_information' must be an object")
    rating = _rating(value, "dhs_criteria.protected_information.rating")
    classification = _required_string(value, "data_classification").lower()
    if classification not in {"low", "medium", "high", "critical", "unknown"}:
        raise QualitativeRiskResponseParseError(
            "LLM response field 'dhs_criteria.protected_information.data_classification' has an invalid value"
        )
    return {
        "question": str(
            value.get("question")
            or "Q2: protected information based on data classification and confidentiality needs."
        ),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "data_classification": classification,
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _dhs_communication_scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.communication_scope' must be an object")
    rating = _rating(value, "dhs_criteria.communication_scope.rating")
    exposure = _required_string(value, "exposure").lower()
    if exposure not in {"air_gapped", "internal_network", "dmz", "public_internet", "unknown"}:
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.communication_scope.exposure' has an invalid value")
    direction = _required_string(value, "direction").lower()
    if direction not in {"none", "internal_only", "external_inbound", "external_bidirectional", "unknown"}:
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.communication_scope.direction' has an invalid value")
    return {
        "question": str(
            value.get("question")
            or "Q3: communication scope based on internal-only versus external bidirectional exposure."
        ),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "exposure": exposure,
        "direction": direction,
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _dhs_sharing_level(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.sharing_level' must be an object")
    rating = _rating(value, "dhs_criteria.sharing_level.rating")
    sharing_scope = _required_string(value, "sharing_scope").lower()
    if sharing_scope not in {"none", "internal_only", "partner", "third_party", "public", "unknown"}:
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.sharing_level.sharing_scope' has an invalid value")
    return {
        "question": str(value.get("question") or "Q4: sharing level based on third-party or partner integration."),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "sharing_scope": sharing_scope,
        "external_parties": _string_list(value.get("external_parties")),
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _dhs_critical_infrastructure(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.critical_infrastructure' must be an object")
    rating = _rating(value, "dhs_criteria.critical_infrastructure.rating")
    dependency_level = _required_string(value, "dependency_level").lower()
    if dependency_level not in {"none", "supporting", "core", "critical", "unknown"}:
        raise QualitativeRiskResponseParseError(
            "LLM response field 'dhs_criteria.critical_infrastructure.dependency_level' has an invalid value"
        )
    return {
        "question": str(
            value.get("question")
            or "Q5: critical infrastructure dependency based on DB, identity, payment, KMS, or gateway role."
        ),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "dependency_level": dependency_level,
        "infrastructure_roles": _string_list(value.get("infrastructure_roles")),
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _dhs_protection_duration(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QualitativeRiskResponseParseError("LLM response field 'dhs_criteria.protection_duration' must be an object")
    rating = _rating(value, "dhs_criteria.protection_duration.rating")
    hndl_exposure = _required_string(value, "hndl_exposure").lower()
    if hndl_exposure not in {"low", "medium", "high", "critical", "unknown"}:
        raise QualitativeRiskResponseParseError(
            "LLM response field 'dhs_criteria.protection_duration.hndl_exposure' has an invalid value"
        )
    return {
        "question": str(
            value.get("question")
            or "Q6: protection duration based on retention period and HNDL exposure."
        ),
        "rating": rating,
        "score": _confidence(value.get("score")),
        "lifespan_years": _optional_non_negative_int(value.get("lifespan_years")),
        "hndl_exposure": hndl_exposure,
        "rationale": _required_string(value, "rationale"),
        "signals": _string_list(value.get("signals")),
    }


def _rating(value: Mapping[str, Any], field_name: str) -> str:
    rating = _required_string(value, "rating").lower()
    if rating not in {"low", "medium", "high", "critical"}:
        raise QualitativeRiskResponseParseError(f"LLM response field '{field_name}' has an invalid value")
    return rating


def _optional_non_negative_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise QualitativeRiskResponseParseError(
            "LLM response field 'dhs_criteria.protection_duration.lifespan_years' must be numeric or null"
        ) from exc
    if parsed < 0:
        raise QualitativeRiskResponseParseError(
            "LLM response field 'dhs_criteria.protection_duration.lifespan_years' must not be negative"
        )
    return parsed


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise QualitativeRiskResponseParseError("LLM response field 'confidence' must be numeric") from exc
    if confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    return round(max(0, min(1, confidence)), 2)
