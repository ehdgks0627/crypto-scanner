import json
import re

from apps.risk.models import RiskScore
from migration_engine import recommend_migration
from risk_engine import llm as llm_client


MIGRATION_SUGGESTION_PROMPT_VERSION = "migration-candidate-suggestion-v1"
LEGACY_ALGORITHM_PATTERN = re.compile(
    r"\b(RSA(?:-\d+)?|ECDSA(?:[ -]?P-?\d+)?|ECDH|ED25519|ED448|X25519|X448|DHE|DH|DIFFIE-HELLMAN|MODP(?:-\d+)?|GROUP\d+)\b",
    re.IGNORECASE,
)


class MigrationSuggestionUnavailable(Exception):
    pass


def snapshot_migration_plan_items(snapshot):
    queryset = (
        RiskScore.objects.filter(snapshot=snapshot)
        .select_related("asset", "asset__target")
        .order_by("-score", "asset_id")
    )
    return [recommend_for_risk_score(risk_score) for risk_score in queryset]


def recommend_for_risk_score(risk_score):
    asset = risk_score.asset
    context = risk_score.factors.get("context", {}) if isinstance(risk_score.factors, dict) else {}
    return recommend_migration(
        asset_id=risk_score.asset_id,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        algorithm=asset.algorithm,
        algorithm_family=asset.algorithm_family,
        risk_score=round(risk_score.score),
        tier=risk_score.tier,
        context=context,
        capabilities=migration_capabilities(asset),
    )


def suggest_migration_for_risk_score(risk_score):
    base_item = recommend_for_risk_score(risk_score)
    options = _allowed_migration_options(base_item)
    prompt = _build_migration_suggestion_prompt(risk_score, base_item, options)
    try:
        completion = llm_client.call_qualitative_risk_llm(prompt)
    except (TimeoutError, llm_client.LlmProviderError, llm_client.LlmProviderUnavailable) as exc:
        raise MigrationSuggestionUnavailable(str(exc)) from exc

    parsed = _parse_migration_suggestion_response(completion.content, options)
    plan_item = _apply_ai_migration_selection(base_item, parsed)
    return {
        "asset_id": risk_score.asset_id,
        "prompt_version": MIGRATION_SUGGESTION_PROMPT_VERSION,
        "plan_item": plan_item,
        "provider": {
            "provider": completion.provider,
            "model": completion.model,
            "usage": dict(completion.usage),
        },
        "fallback": parsed["fallback"],
        "llm_trace": {
            "request": {
                "version": prompt["version"],
                "system": prompt["system"],
                "user": prompt["user"],
                "payload": prompt["payload"],
                "response_schema": prompt["response_schema"],
            },
            "response": {
                "raw": completion.content,
                "parsed": parsed["parsed_response"],
            },
        },
    }


def migration_capabilities(asset):
    capabilities = {"inventory_fresh"}
    if asset.target:
        capabilities.add("owner_known")
        if asset.target.agent_enabled:
            capabilities.update({"config_policy", "rescan_validation"})
        if asset.target.context and asset.target.context.get("service_role"):
            capabilities.add("canary_supported")
    if asset.asset_type in {"certificate", "key"}:
        capabilities.add("rollback_supported")
    return sorted(capabilities)


def _allowed_migration_options(base_item):
    recommendation = base_item["recommendation"]
    options = [
        {
            "candidate_id": "policy_default",
            "label": "Policy default PQC target",
            "recommendation": dict(recommendation),
        }
    ]
    for index, alternative in enumerate(base_item.get("alternatives") or [], start=1):
        strategy = alternative.get("strategy") or "replace"
        target_algorithm = alternative.get("target_algorithm") or recommendation["target_algorithm"]
        target_set = _split_algorithm_set(target_algorithm)
        options.append(
            {
                "candidate_id": f"alternative_{index}",
                "label": alternative.get("trade_off") or "Policy alternative",
                "recommendation": {
                    **recommendation,
                    "strategy": strategy,
                    "target_algorithm": target_algorithm,
                    "target_algorithm_set": target_set,
                    "final_algorithm_set": target_set,
                    "phase": "replace_now" if strategy == "replace" else recommendation["phase"],
                    "rationale": alternative.get("trade_off") or recommendation["rationale"],
                    "confidence": min(float(recommendation.get("confidence") or 0.82), 0.76),
                },
            }
        )
    return options


def _split_algorithm_set(value):
    parts = [part.strip() for part in str(value or "").split("+")]
    return [part for part in parts if part]


def _build_migration_suggestion_prompt(risk_score, base_item, options):
    payload = {
        "enriched_cbom": _enriched_cbom_payload(risk_score),
        "policy_default": _option_payload(options[0]),
        "allowed_candidates": [_option_payload(option) for option in options],
        "guardrails": [
            "Select exactly one allowed candidate_id.",
            "Do not invent algorithms or modify algorithm names.",
            "Use Enriched CBOM context only as evidence for choosing among allowed candidates.",
            "If evidence is weak, select policy_default.",
        ],
    }
    schema = {
        "selected_candidate_id": "one candidate_id from allowed_candidates",
        "confidence": "number between 0 and 1",
        "rationale": "one concise sentence using only supplied Enriched CBOM evidence",
        "evidence": ["short strings copied or derived from supplied fields"],
    }
    return {
        "version": MIGRATION_SUGGESTION_PROMPT_VERSION,
        "system": (
            "You choose a PQC migration recommendation for one cryptographic asset. "
            "You must choose only from the supplied allowed_candidates. "
            "Return concise JSON only."
        ),
        "user": (
            "Choose the best PQC migration candidate for this asset.\n"
            "Use the Enriched CBOM context to decide whether the policy default or an allowed alternative is more appropriate.\n"
            "Do not invent algorithm names. Do not recommend changes outside allowed_candidates.\n\n"
            f"Payload:\n{json.dumps(payload, sort_keys=True, indent=2)}\n\n"
            f"Required JSON schema:\n{json.dumps(schema, sort_keys=True, indent=2)}"
        ),
        "payload": payload,
        "response_schema": schema,
    }


def _enriched_cbom_payload(risk_score):
    from apps.assets import services as asset_services

    asset = risk_score.asset
    override = getattr(asset, "context_override", None)
    target = asset.target
    return {
        "asset": {
            "id": asset.id,
            "snapshot_id": asset.snapshot_id,
            "bom_ref": asset.bom_ref,
            "name": asset.name,
            "asset_class": asset.asset_class,
            "asset_type": asset.asset_type,
            "algorithm": _redact_legacy_algorithm(asset.algorithm),
            "algorithm_family": _redact_legacy_algorithm(asset.algorithm_family),
            "metadata": _redact_legacy_algorithms(asset.metadata or {}),
        },
        "target": None
        if not target
        else {
            "id": target.id,
            "host": target.host,
            "port": target.port,
            "transport": target.transport,
            "protocol_hint": target.protocol_hint,
            "sni": target.sni,
            "agent_enabled": target.agent_enabled,
            "context": target.context or {},
        },
        "effective_context": asset_services.effective_context(asset, override),
        "context_sources": asset_services.context_sources(asset, override),
        "risk": {
            "score": round(risk_score.score),
            "tier": risk_score.tier,
            "factors": _redact_legacy_algorithms(risk_score.factors or {}),
        },
    }


def _redact_legacy_algorithms(value):
    if isinstance(value, dict):
        return {key: _redact_legacy_algorithms(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_legacy_algorithms(item) for item in value]
    if isinstance(value, str):
        return _redact_legacy_algorithm(value)
    return value


def _redact_legacy_algorithm(value):
    if not isinstance(value, str):
        return value
    return LEGACY_ALGORITHM_PATTERN.sub("legacy-public-key", value)


def _option_payload(option):
    recommendation = option["recommendation"]
    return {
        "candidate_id": option["candidate_id"],
        "label": option["label"],
        "transition_mode": _public_transition_mode(recommendation["strategy"]),
        "target_algorithm": recommendation["target_algorithm"],
        "target_algorithm_set": recommendation["target_algorithm_set"],
        "final_algorithm_set": recommendation["final_algorithm_set"],
        "rationale": recommendation["rationale"],
    }


def _public_transition_mode(strategy):
    if strategy == "no_change":
        return "monitor"
    return "pqc_transition"


def _parse_migration_suggestion_response(text, options):
    option_by_id = {option["candidate_id"]: option for option in options}
    parsed_response = {}
    fallback = {"used": False, "reason": None}
    try:
        data = _extract_json_object(text)
    except ValueError:
        data = {}
        fallback = {"used": True, "reason": "invalid_json"}

    parsed_response = data if isinstance(data, dict) else {}
    selected_id = str(parsed_response.get("selected_candidate_id") or parsed_response.get("candidate_id") or "").strip()
    selected = option_by_id.get(selected_id)
    if selected is None:
        selected = _find_option_by_strategy_or_target(parsed_response, options)
    if selected is None:
        selected = options[0]
        fallback = {"used": True, "reason": fallback["reason"] or "candidate_not_allowed"}

    return {
        "option": selected,
        "confidence": _confidence_or_none(parsed_response.get("confidence")),
        "rationale": _string_or_none(parsed_response.get("rationale")),
        "evidence": _string_list(parsed_response.get("evidence")),
        "fallback": fallback,
        "parsed_response": parsed_response,
    }


def _find_option_by_strategy_or_target(data, options):
    target = str(data.get("target_algorithm") or "").strip()
    strategy = str(data.get("strategy") or "").strip()
    for option in options:
        recommendation = option["recommendation"]
        if target and recommendation["target_algorithm"] == target and (not strategy or recommendation["strategy"] == strategy):
            return option
    return None


def _apply_ai_migration_selection(base_item, parsed):
    selected = parsed["option"]
    recommendation = dict(selected["recommendation"])
    if parsed["rationale"]:
        recommendation["rationale"] = parsed["rationale"]
    if parsed["confidence"] is not None:
        recommendation["confidence"] = parsed["confidence"]
    return {
        **base_item,
        "recommendation": recommendation,
        "ai_recommendation": {
            "source": "llm_guarded_allowed_candidates",
            "selected_candidate_id": selected["candidate_id"],
            "evidence": parsed["evidence"],
            "fallback": parsed["fallback"],
        },
    }


def _extract_json_object(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("migration suggestion response did not include a JSON object")


def _confidence_or_none(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(1.0, parsed)), 2)


def _string_or_none(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:8]
