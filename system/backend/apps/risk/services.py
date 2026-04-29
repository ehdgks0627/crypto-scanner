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
        "score": risk_score.score,
        "tier": risk_score.tier,
        "factors": risk_score.factors,
        "computed_at": serialize_dt(risk_score.computed_at),
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
