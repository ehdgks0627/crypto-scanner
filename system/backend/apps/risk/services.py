from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import AsyncJob, QueuedTask
from apps.jobs.services import enqueue_task, serialize_dt
from apps.risk.models import RiskScore, RiskWeights
from risk_engine import DEFAULT_WEIGHTS, compute_dhs_risk, compute_risk, normalize_weights


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
        "dhs_risk": _serialized_dhs_risk(risk_score),
        "computed_at": serialize_dt(risk_score.computed_at),
    }


def serialize_asset_risk_summary(risk_score):
    return {
        "score": round(risk_score.score),
        "tier": risk_score.tier,
        "dhs_risk": _serialized_dhs_risk(risk_score),
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
        "dhs_risk": _serialized_dhs_risk(risk_score),
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


def default_weights_dict() -> dict[str, float]:
    weights = RiskWeights.objects.order_by("id").first()
    if not weights:
        return dict(DEFAULT_WEIGHTS)
    return {
        "wA": weights.wA,
        "wD": weights.wD,
        "wE": weights.wE,
        "wL": weights.wL,
        "wC": weights.wC,
    }


def persist_default_weights(weights: dict[str, float]) -> RiskWeights:
    row = RiskWeights.objects.order_by("id").first() or RiskWeights()
    for field, value in weights.items():
        setattr(row, field, value)
    row.save()
    return row


def recompute_snapshot_risks(snapshot_id: int, weights: dict | None = None) -> dict:
    from apps.assets.models import Asset

    resolved_weights = _resolved_weights(weights)
    assets = (
        Asset.objects.filter(snapshot_id=snapshot_id, asset_class="crypto")
        .select_related("target", "context_override")
        .order_by("id")
    )
    updated_count = 0
    for asset in assets:
        _upsert_asset_risk(asset, resolved_weights)
        updated_count += 1
    return {"snapshot_id": snapshot_id, "updated_scores_count": updated_count}


def recompute_asset_risk(asset_id: int, weights: dict | None = None) -> dict:
    from apps.assets.models import Asset

    asset = Asset.objects.select_related("target", "context_override").get(id=asset_id)
    _upsert_asset_risk(asset, _resolved_weights(weights))
    return {"asset_id": asset.id, "snapshot_id": asset.snapshot_id, "updated_scores_count": 1}


def recompute_target_risks(target_id: int, weights: dict | None = None) -> dict:
    from apps.assets.models import Asset

    resolved_weights = _resolved_weights(weights)
    assets = (
        Asset.objects.filter(target_id=target_id, asset_class="crypto")
        .select_related("target", "context_override")
        .order_by("id")
    )
    updated_count = 0
    snapshot_ids = set()
    for asset in assets:
        _upsert_asset_risk(asset, resolved_weights)
        updated_count += 1
        if asset.snapshot_id:
            snapshot_ids.add(asset.snapshot_id)
    return {"target_id": target_id, "snapshot_ids": sorted(snapshot_ids), "updated_scores_count": updated_count}


def run_recompute_payload(payload: dict) -> dict:
    weights = _resolved_weights(payload.get("weights"))
    if payload.get("persist_weights_as_default"):
        persist_default_weights(weights)
    if payload.get("asset_id"):
        return recompute_asset_risk(payload["asset_id"], weights)
    if payload.get("target_id"):
        return recompute_target_risks(payload["target_id"], weights)
    if payload.get("snapshot_id"):
        return recompute_snapshot_risks(payload["snapshot_id"], weights)
    raise ValueError("recompute payload requires snapshot_id, target_id, or asset_id")


def process_next_recompute_task() -> dict | None:
    task = (
        QueuedTask.objects.filter(task_name="recompute", status=QueuedTask.QUEUED, available_at__lte=timezone.now())
        .order_by("available_at", "id")
        .first()
    )
    if not task:
        return None
    return process_recompute_task(task.id)


def process_recompute_task(task_id: int) -> dict:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        if task.status == QueuedTask.CANCELLED:
            return {}
        if task.status != QueuedTask.QUEUED:
            raise ValueError(f"QueuedTask {task.id} is not queued")
        async_job = task.async_job
        now = timezone.now()
        task.status = QueuedTask.RUNNING
        task.attempts += 1
        task.locked_at = now
        task.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        if async_job:
            if async_job.status == AsyncJob.CANCELLED:
                task.status = QueuedTask.CANCELLED
                task.save(update_fields=["status", "updated_at"])
                return {}
            async_job.status = AsyncJob.RUNNING
            async_job.started_at = async_job.started_at or now
            async_job.progress = {"current": 0, "total": None, "percent": 0}
            async_job.save(update_fields=["status", "started_at", "progress", "updated_at"])

    try:
        result = run_recompute_payload(task.payload)
    except Exception as exc:
        _fail_recompute_task(task_id, exc)
        raise

    _complete_recompute_task(task_id, result)
    return result


def _upsert_asset_risk(asset, weights: dict[str, float]) -> RiskScore:
    from apps.assets import services as asset_services

    override = getattr(asset, "context_override", None)
    context = asset_services.effective_context(asset, override)
    sources = asset_services.context_sources(asset, override)
    target_ip = asset.target.ip if asset.target else None
    protocol_hint = asset.target.protocol_hint if asset.target else None
    result = compute_risk(
        algorithm=asset.algorithm,
        algorithm_family=asset.algorithm_family,
        asset_type=asset.asset_type,
        context=context,
        context_sources=sources,
        target_ip=target_ip,
        protocol_hint=protocol_hint,
        weights=weights,
    )
    factors = {
        **result.factors,
        "raw": result.raw,
        "weighted_raw": result.weighted_raw,
        "weights": result.weights,
        "sources": result.sources,
        "context": context,
        "engine_version": result.engine_version,
    }
    dhs_risk = _compute_asset_dhs_risk(asset)
    if dhs_risk:
        factors["dhs_risk"] = dhs_risk
    existing = list(RiskScore.objects.filter(asset=asset).order_by("id"))
    if existing:
        risk_score = existing[0]
        if len(existing) > 1:
            RiskScore.objects.filter(id__in=[row.id for row in existing[1:]]).delete()
        risk_score.snapshot = asset.snapshot
        risk_score.score = result.score
        risk_score.tier = result.tier
        risk_score.factors = factors
        risk_score.computed_at = timezone.now()
        risk_score.save(update_fields=["snapshot", "score", "tier", "factors", "computed_at"])
        return risk_score
    return RiskScore.objects.create(
        snapshot=asset.snapshot,
        asset=asset,
        score=result.score,
        tier=result.tier,
        factors=factors,
    )


def _compute_asset_dhs_risk(asset) -> dict | None:
    try:
        assessment = asset.qualitative_assessment
    except ObjectDoesNotExist:
        return None
    return compute_dhs_risk(assessment.dhs_criteria).to_dict()


def _serialized_dhs_risk(risk_score) -> dict | None:
    if not risk_score or not isinstance(risk_score.factors, dict):
        return None
    value = risk_score.factors.get("dhs_risk")
    return value if isinstance(value, dict) else None


def _resolved_weights(weights: dict | None = None) -> dict[str, float]:
    source = weights if weights is not None else default_weights_dict()
    return normalize_weights(source)


def _complete_recompute_task(task_id: int, result: dict) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        task.status = QueuedTask.COMPLETED
        task.last_error = None
        task.save(update_fields=["status", "last_error", "updated_at"])
        if task.async_job:
            async_job = task.async_job
            async_job.status = AsyncJob.COMPLETED
            async_job.progress = {"current": result.get("updated_scores_count", 0), "total": result.get("updated_scores_count", 0), "percent": 100}
            async_job.result = result
            async_job.error = None
            async_job.finished_at = timezone.now()
            async_job.save(update_fields=["status", "progress", "result", "error", "finished_at", "updated_at"])


def _fail_recompute_task(task_id: int, exc: Exception) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        task.status = QueuedTask.FAILED
        task.last_error = str(exc)
        task.save(update_fields=["status", "last_error", "updated_at"])
        if task.async_job:
            async_job = task.async_job
            async_job.status = AsyncJob.FAILED
            async_job.error = {"message": str(exc)}
            async_job.finished_at = timezone.now()
            async_job.save(update_fields=["status", "error", "finished_at", "updated_at"])
