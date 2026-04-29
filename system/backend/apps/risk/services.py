from apps.jobs.models import AsyncJob
from apps.jobs.services import enqueue_task, serialize_dt


class EnqueueUnavailable(Exception):
    pass


def enqueue_recompute(async_job) -> None:
    enqueue_task("recompute", async_job.request_payload, async_job=async_job)


def serialize_risk_score(risk_score):
    return {
        "asset_id": risk_score.asset_id,
        "asset_name": risk_score.asset.name,
        "asset_type": risk_score.asset.asset_type,
        "score": round(risk_score.score),
        "tier": risk_score.tier,
        "factors": normalize_factors(risk_score.factors),
        "computed_at": serialize_dt(risk_score.computed_at),
    }


def normalize_factors(factors):
    source = factors or {}
    return {
        key: source.get(key, source.get(key.upper(), 0))
        for key in ("a", "d", "e", "l", "c")
    }


def serialize_risk_detail(risk_score):
    factors = normalize_factors(risk_score.factors)
    return {
        "score": round(risk_score.score),
        "tier": risk_score.tier,
        "factor_a": factors["a"],
        "factor_d": factors["d"],
        "factor_e": factors["e"],
        "factor_l": factors["l"],
        "factor_c": factors["c"],
        "weights": risk_score.factors.get("weights", {"wA": 1, "wD": 1, "wE": 1, "wL": 1, "wC": 1})
        if isinstance(risk_score.factors, dict)
        else {"wA": 1, "wD": 1, "wE": 1, "wL": 1, "wC": 1},
    }


def create_recompute_job(snapshot_id: int, payload: dict):
    async_job = AsyncJob.objects.create(
        kind="recompute",
        status=AsyncJob.PENDING,
        request_payload={"snapshot_id": snapshot_id, **payload},
    )
    async_job.resource_id = async_job.id
    async_job.save(update_fields=["resource_id"])
    enqueue_recompute(async_job)
    return async_job
