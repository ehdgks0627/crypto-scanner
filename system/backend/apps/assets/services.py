import json
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from apps.jobs.models import AsyncJob, QueuedTask
from apps.jobs.services import enqueue_task, serialize_dt
from apps.risk import services as risk_services
from risk_engine.prompts import (
    QualitativeRiskResponseParseError,
    build_qualitative_risk_prompt,
    parse_qualitative_risk_response,
)


CONTEXT_FIELDS = ["sensitivity", "lifespan_years", "criticality", "exposure", "service_role"]
QUALITATIVE_TASK_NAME = "qualitative_assessment"
QUALITATIVE_PROVIDER = "mock-rulebook"
QUALITATIVE_FALLBACK_PROVIDER = "mock-rulebook-fallback"
QUALITATIVE_PROMPT_METADATA_KEYS = {"llm_cache", "llm_fallback"}
QUANTUM_VULNERABLE_FAMILIES = {"RSA", "DSA", "ECDSA", "ECDH", "DH"}
CONTEXT_LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}
EXPOSURE_LEVELS = {"air_gapped": 0, "internal_network": 1, "dmz": 2, "public_internet": 3}


class EnqueueUnavailable(Exception):
    pass


def enqueue_asset_recompute(async_job) -> None:
    enqueue_task("recompute", async_job.request_payload, async_job=async_job)


def empty_context():
    return {field: None for field in CONTEXT_FIELDS}


def override_to_dict(override):
    if override is None:
        return empty_context()
    return {field: getattr(override, field) if field in override.override_keys else None for field in CONTEXT_FIELDS}


def target_context(asset):
    if not asset.target:
        return empty_context()
    return {**empty_context(), **(asset.target.context or {})}


def effective_context(asset, override=None):
    override_values = override_to_dict(override)
    target_values = target_context(asset)
    return {
        field: override_values[field] if override_values[field] is not None else target_values[field]
        for field in CONTEXT_FIELDS
    }


def context_sources(asset, override=None):
    override_values = override_to_dict(override)
    target_values = target_context(asset)
    sources = {}
    for field in CONTEXT_FIELDS:
        if override_values[field] is not None:
            sources[field] = "asset_override"
        elif target_values[field] is not None:
            sources[field] = "target"
        else:
            sources[field] = "heuristic"
    return sources


def create_recompute_job(asset_id: int):
    job = AsyncJob.objects.create(
        kind="recompute",
        status=AsyncJob.PENDING,
        request_payload={"asset_id": asset_id, "reason": "asset_context_changed"},
    )
    job.resource_id = job.id
    job.save(update_fields=["resource_id"])
    enqueue_asset_recompute(job)
    return job


def enqueue_qualitative_assessment(asset_id: int) -> QueuedTask:
    return enqueue_task(QUALITATIVE_TASK_NAME, {"asset_id": asset_id})


def process_next_qualitative_assessment_task() -> dict | None:
    task = (
        QueuedTask.objects.filter(task_name=QUALITATIVE_TASK_NAME, status=QueuedTask.QUEUED, available_at__lte=timezone.now())
        .order_by("available_at", "id")
        .first()
    )
    if not task:
        return None
    return process_qualitative_assessment_task(task.id)


def process_qualitative_assessment_task(task_id: int) -> dict:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        if task.status == QueuedTask.CANCELLED:
            return {}
        if task.status != QueuedTask.QUEUED:
            raise ValueError(f"QueuedTask {task.id} is not queued")
        now = timezone.now()
        task.status = QueuedTask.RUNNING
        task.attempts += 1
        task.locked_at = now
        task.save(update_fields=["status", "attempts", "locked_at", "updated_at"])

    try:
        asset_id = int(task.payload["asset_id"])
        assessment = refresh_qualitative_assessment(asset_id)
        result = {
            "asset_id": asset_id,
            "assessment_id": assessment.id,
            "provider": assessment.provider,
        }
    except Exception as exc:
        _fail_qualitative_assessment_task(task_id, exc)
        raise

    _complete_qualitative_assessment_task(task_id, result)
    return result


def refresh_qualitative_assessment(asset_or_id):
    from apps.assets.models import Asset, QualitativeAssessment

    if isinstance(asset_or_id, Asset):
        asset = asset_or_id
    else:
        asset = Asset.objects.select_related("target").get(id=asset_or_id)
    existing = QualitativeAssessment.objects.filter(asset=asset).first()
    defaults = generate_qualitative_assessment(asset, cached_assessment=existing)
    if defaults is None:
        return existing
    assessment, _created = QualitativeAssessment.objects.update_or_create(
        asset=asset,
        defaults=defaults,
    )
    return assessment


def generate_qualitative_assessment(asset, cached_assessment=None):
    override = getattr(asset, "context_override", None)
    context = effective_context(asset, override)
    sources = context_sources(asset, override)
    risk_score = asset.risk_scores.order_by("-id").first()
    score = risk_score.score if risk_score else _heuristic_qualitative_score(asset, context)
    prompt = build_qualitative_risk_prompt(
        asset=_qualitative_asset_payload(asset),
        context=context,
        context_sources=sources,
        operational_context=_qualitative_operational_context(asset, context, sources),
        risk=_qualitative_risk_payload(risk_score, score),
    )
    cache_key = _qualitative_prompt_cache_key(prompt["payload"])
    if _qualitative_cache_hit(cached_assessment, prompt, cache_key):
        return None

    fallback_response = _heuristic_qualitative_response(asset, context, risk_score, score)
    fallback_metadata = {"used": False, "reason": None}
    provider = QUALITATIVE_PROVIDER
    try:
        raw_response = _mock_qualitative_llm_response(fallback_response)
        parsed_response = parse_qualitative_risk_response(raw_response)
    except (QualitativeRiskResponseParseError, TimeoutError) as exc:
        provider = QUALITATIVE_FALLBACK_PROVIDER
        fallback_metadata = {"used": True, "reason": exc.__class__.__name__}
        parsed_response = fallback_response
    return {
        "provider": provider,
        "prompt_version": prompt["version"],
        "prompt_payload": {
            **prompt["payload"],
            "llm_cache": {"key": cache_key},
            "llm_fallback": fallback_metadata,
        },
        **parsed_response,
    }


def _qualitative_prompt_cache_key(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _qualitative_cache_hit(assessment, prompt: dict, cache_key: str) -> bool:
    if assessment is None or assessment.prompt_version != prompt["version"]:
        return False
    prompt_payload = assessment.prompt_payload or {}
    metadata = prompt_payload.get("llm_cache") or {}
    if metadata.get("key") == cache_key:
        return True
    cached_payload = {
        key: value
        for key, value in prompt_payload.items()
        if key not in QUALITATIVE_PROMPT_METADATA_KEYS
    }
    return cached_payload == prompt["payload"]


def _heuristic_qualitative_response(asset, context, risk_score, score):
    return {
        "summary": _qualitative_summary(asset, context, score),
        "threat_scenarios": _qualitative_threat_scenarios(asset, context),
        "migration_recommendation": _qualitative_migration_recommendation(asset, score),
        "confidence": _qualitative_confidence(asset, context, risk_score, score),
    }


def _mock_qualitative_llm_response(payload: dict) -> str:
    return "Mock qualitative assessment:\n```json\n" + json.dumps(payload, sort_keys=True) + "\n```"


def _qualitative_asset_payload(asset):
    return {
        "id": asset.id,
        "snapshot_id": asset.snapshot_id,
        "bom_ref": asset.bom_ref,
        "name": asset.name,
        "asset_class": asset.asset_class,
        "asset_type": asset.asset_type,
        "algorithm": asset.algorithm,
        "algorithm_family": asset.algorithm_family,
        "target_label": target_label(asset),
        "metadata": asset.metadata or {},
    }


def _qualitative_risk_payload(risk_score, fallback_score):
    if risk_score:
        return {
            "score": round(risk_score.score),
            "tier": risk_score.tier,
            "factors": risk_score.factors,
            "source": "risk_score",
        }
    return {
        "score": round(fallback_score),
        "tier": None,
        "factors": {},
        "source": "heuristic",
    }


def _qualitative_operational_context(asset, context, sources):
    metadata = asset.metadata or {}
    target = asset.target
    return {
        "connected_service": None if not target else {
            "label": target_label(asset),
            "display_name": target.display_name,
            "host": target.host,
            "ip": target.ip,
            "port": target.port,
            "transport": target.transport,
            "protocol_hint": target.protocol_hint,
            "sni": target.sni,
        },
        "file_paths": _metadata_paths(metadata),
        "source_scanners": _metadata_list(metadata.get("source_scanners") or metadata.get("scanner")),
        "data_classification": {
            "level": context.get("sensitivity") or "unknown",
            "source": sources.get("sensitivity", "heuristic"),
        },
        "communication_scope": {
            "exposure": context.get("exposure") or "unknown",
            "source": sources.get("exposure", "heuristic"),
        },
        "service_role": {
            "value": context.get("service_role") or (target.protocol_hint if target else None) or asset.asset_type,
            "source": sources.get("service_role", "heuristic"),
        },
    }


def _metadata_paths(metadata):
    values = []
    for key in ["path", "source_paths", "certificate_paths", "private_key_paths", "referenced_by"]:
        values.extend(_metadata_list(metadata.get(key)))
    return _dedupe_values([value for value in values if isinstance(value, str) and value.startswith("/")])


def _metadata_list(value):
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


def _dedupe_values(values):
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _family_key(asset):
    return (asset.algorithm_family or "").upper()


def _is_quantum_vulnerable(asset):
    return _family_key(asset) in QUANTUM_VULNERABLE_FAMILIES


def _heuristic_qualitative_score(asset, context):
    score = 55 if _is_quantum_vulnerable(asset) else 15
    score += {"certificate": 5, "key": 8, "ssh_host_key": 10, "ssh_user_key": 10}.get(asset.asset_type, 0)
    score += CONTEXT_LEVELS.get(context.get("sensitivity"), 0) * 4
    score += CONTEXT_LEVELS.get(context.get("criticality"), 0) * 5
    score += EXPOSURE_LEVELS.get(context.get("exposure"), 0) * 5
    lifespan = context.get("lifespan_years")
    if lifespan is not None:
        if lifespan >= 10:
            score += 10
        elif lifespan >= 5:
            score += 6
        elif lifespan > 0:
            score += 2
    return max(0, min(100, score))


def _qualitative_summary(asset, context, score):
    name = asset.name or asset.bom_ref or f"asset {asset.id}"
    algorithm = asset.algorithm or asset.algorithm_family or "unknown algorithm"
    target = target_label(asset) or "unmapped target"
    exposure = context.get("exposure") or "unknown exposure"
    role = context.get("service_role") or asset.asset_type or "unknown role"
    if score >= 80:
        posture = "near-term PQC migration planning is recommended."
    elif score >= 60:
        posture = "migration planning should be scheduled before the protected data or identity lifetime grows."
    elif _is_quantum_vulnerable(asset):
        posture = "quantum exposure exists, but the current context lowers the immediate operational priority."
    else:
        posture = "no immediate quantum-driven replacement is indicated from the current context."
    return f"{name} uses {algorithm} on {target}. For {role} with {exposure}, {posture}"


def _qualitative_threat_scenarios(asset, context):
    scenarios = []
    if _is_quantum_vulnerable(asset):
        scenarios.append("harvest_now_decrypt_later")
    lifespan = context.get("lifespan_years")
    if lifespan is not None and lifespan >= 5:
        scenarios.append("long_lived_data_exposure")
    if context.get("exposure") in {"public_internet", "dmz"}:
        scenarios.append("network_exposed_cryptographic_service")
    if asset.asset_type in {"certificate", "key", "ssh_host_key", "ssh_user_key"}:
        scenarios.append("service_identity_compromise")
    return scenarios or ["cryptographic_inventory_drift"]


def _qualitative_migration_recommendation(asset, score):
    family = _family_key(asset)
    priority = "Prioritize" if score >= 80 else "Plan"
    if family == "RSA":
        return f"{priority} a hybrid RSA/PQC transition and validate peer compatibility before replacing this asset."
    if family in {"ECDSA", "DSA"}:
        return f"{priority} replacement with ML-DSA or a hybrid certificate path where clients require classical trust."
    if family in {"ECDH", "DH"}:
        return f"{priority} migration to ML-KEM or a hybrid key-establishment mode for supported protocols."
    if family.startswith("ML-") or family in {"SLH-DSA", "FN-DSA"}:
        return "Maintain the current PQC posture and monitor interoperability, lifecycle, and policy requirements."
    return f"{priority} owner review and select a PQC or hybrid alternative if this asset protects long-lived data."


def _qualitative_confidence(asset, context, risk_score, score):
    populated_context = sum(1 for value in context.values() if value is not None)
    confidence = 0.42
    confidence += 0.18 if risk_score else 0.04
    confidence += min(score, 100) / 1000
    confidence += min(populated_context * 0.025, 0.12)
    confidence += 0.05 if asset.algorithm_family else 0
    confidence += 0.03 if asset.algorithm else 0
    confidence += 0.03 if asset.target_id else 0
    if _is_quantum_vulnerable(asset):
        confidence += 0.03
    return round(max(0.35, min(0.95, confidence)), 2)


def _complete_qualitative_assessment_task(task_id: int, result: dict) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        task.status = QueuedTask.COMPLETED
        task.last_error = None
        task.save(update_fields=["status", "last_error", "updated_at"])


def _fail_qualitative_assessment_task(task_id: int, exc: Exception) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        task.status = QueuedTask.FAILED
        task.last_error = str(exc)
        task.save(update_fields=["status", "last_error", "updated_at"])


def serialize_asset_summary(asset, risk_score=None):
    risk = None
    if risk_score:
        risk = {"score": round(risk_score.score), "tier": risk_score.tier}
    return {
        "id": asset.id,
        "snapshot_id": asset.snapshot_id,
        "bom_ref": asset.bom_ref,
        "name": asset.name,
        "asset_class": asset.asset_class,
        "asset_type": asset.asset_type,
        "target_id": asset.target_id,
        "target_label": target_label(asset),
        "summary": asset_summary(asset),
        "risk": risk,
    }


def serialize_asset_detail(asset):
    override = getattr(asset, "context_override", None)
    risk_score = asset.risk_scores.order_by("-id").first()
    qualitative = getattr(asset, "qualitative_assessment", None)
    return {
        "id": asset.id,
        "snapshot_id": asset.snapshot_id,
        "bom_ref": asset.bom_ref,
        "name": asset.name,
        "asset_class": asset.asset_class,
        "asset_type": asset.asset_type,
        "crypto_properties": crypto_properties(asset),
        "properties": asset_properties(asset),
        "discovered_at": serialize_dt(asset.created_at),
        "target": None if not asset.target else {"id": asset.target.id, "host": asset.target.host, "port": asset.target.port},
        "effective_context": effective_context(asset, override),
        "context_override": override_to_dict(override),
        "context_sources": context_sources(asset, override),
        "risk": risk_services.serialize_risk_detail(risk_score) if risk_score else None,
        "qualitative": serialize_qualitative(qualitative) if qualitative else None,
        "dependencies": serialize_dependencies(asset),
        "history": serialize_history(asset),
    }


def target_label(asset):
    if not asset.target:
        return None
    return f"{asset.target.host}:{asset.target.port}"


def asset_summary(asset):
    summary = {
        "algorithm": asset.algorithm,
        "algorithm_family": asset.algorithm_family,
    }
    metadata = asset.metadata or {}
    for key in ["scanner", "path", "fingerprint_sha256", "in_use", "dormant", "merged"]:
        if key in metadata:
            summary[key] = metadata[key]
    return summary


def crypto_properties(asset):
    properties = {
        "algorithm": asset.algorithm,
        "algorithm_family": asset.algorithm_family,
    }
    metadata = asset.metadata or {}
    if metadata.get("key_size_bits") is not None:
        properties["key_size_bits"] = metadata["key_size_bits"]
    if metadata.get("fingerprint_sha256"):
        properties["fingerprint_sha256"] = metadata["fingerprint_sha256"]
    return properties


def asset_properties(asset):
    properties = {
        "bom_ref": asset.bom_ref,
    }
    metadata = asset.metadata or {}
    for key in [
        "scanner",
        "type",
        "path",
        "format",
        "minimum_tls_version",
        "in_use",
        "dormant",
        "referenced_by",
        "source_scanners",
        "source_paths",
        "source_bom_refs",
        "merged",
    ]:
        if key in metadata and metadata[key] is not None:
            properties[key] = metadata[key]
    return properties


def serialize_dependencies(asset):
    return {
        "dependsOn": [
            dependency_item(edge.target_asset, edge)
            for edge in asset.dependency_edges.select_related("target_asset").order_by("target_asset__bom_ref")
        ],
        "dependedBy": [
            dependency_item(edge.source_asset, edge)
            for edge in asset.depended_by_edges.select_related("source_asset").order_by("source_asset__bom_ref")
        ],
    }


def dependency_item(asset, edge):
    return {
        "id": asset.id,
        "bom_ref": asset.bom_ref,
        "name": asset.name,
        "semantic": edge.semantic or edge.relation_type,
    }


def serialize_history(asset):
    from apps.risk.models import RiskScore

    items = []
    for risk_score in RiskScore.objects.filter(asset__bom_ref=asset.bom_ref).select_related("snapshot").order_by("snapshot__created_at", "id"):
        items.append(
            {
                "snapshot_id": risk_score.snapshot_id,
                "score": round(risk_score.score),
                "tier": risk_score.tier,
                "snapshot_created_at": serialize_dt(risk_score.snapshot.created_at),
            }
        )
    return items


def serialize_qualitative(assessment):
    return {
        "provider": assessment.provider,
        "prompt_version": assessment.prompt_version,
        "summary": assessment.summary,
        "threat_scenarios": assessment.threat_scenarios,
        "migration_recommendation": assessment.migration_recommendation,
        "confidence": assessment.confidence,
        "generated_at": serialize_dt(assessment.generated_at),
    }
