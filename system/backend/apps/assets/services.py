from apps.jobs.models import AsyncJob
from apps.jobs.services import enqueue_task, serialize_dt


CONTEXT_FIELDS = ["sensitivity", "lifespan_years", "criticality", "exposure", "service_role"]


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


def serialize_asset_summary(asset, risk_score=None):
    risk = None
    if risk_score:
        risk = {"score": risk_score.score, "tier": risk_score.tier}
    return {
        "id": asset.id,
        "name": asset.name,
        "asset_class": asset.asset_class,
        "asset_type": asset.asset_type,
        "target_id": asset.target_id,
        "risk": risk,
    }


def serialize_asset_detail(asset):
    override = getattr(asset, "context_override", None)
    return {
        "id": asset.id,
        "name": asset.name,
        "asset_class": asset.asset_class,
        "asset_type": asset.asset_type,
        "target": None if not asset.target else {"id": asset.target.id, "host": asset.target.host},
        "effective_context": effective_context(asset, override),
        "context_override": override_to_dict(override),
        "context_sources": context_sources(asset, override),
    }


def serialize_qualitative(assessment):
    return {
        "provider": assessment.provider,
        "summary": assessment.summary,
        "threat_scenarios": assessment.threat_scenarios,
        "migration_recommendation": assessment.migration_recommendation,
        "confidence": assessment.confidence,
        "generated_at": serialize_dt(assessment.generated_at),
    }
