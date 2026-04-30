from __future__ import annotations

from django.utils import timezone

from apps.assets.models import Asset
from apps.jobs import services as job_services
from apps.performance.models import AssetPerformanceResult, PerformanceEvaluationRun
from apps.snapshots.models import CbomSnapshot
from performance_engine import DEFAULT_THRESHOLDS, evaluate_asset_performance, summarize_results


class InvalidPerformanceResult(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def create_run(snapshot: CbomSnapshot, payload: dict) -> PerformanceEvaluationRun:
    baseline_snapshot_id = payload.get("baseline_snapshot_id")
    baseline_snapshot = None
    if baseline_snapshot_id is not None:
        baseline_snapshot = CbomSnapshot.objects.filter(id=baseline_snapshot_id).first()
        if baseline_snapshot is None:
            raise InvalidPerformanceResult("baseline_snapshot_id does not exist.", {"baseline_snapshot_id": baseline_snapshot_id})
        if baseline_snapshot.id == snapshot.id:
            raise InvalidPerformanceResult("baseline_snapshot_id must be different from snapshot_id.", {"baseline_snapshot_id": baseline_snapshot_id})

    return PerformanceEvaluationRun.objects.create(
        snapshot=snapshot,
        baseline_snapshot=baseline_snapshot,
        trigger=payload.get("trigger", "manual"),
        profile=payload.get("profile", "smoke"),
        status=PerformanceEvaluationRun.PENDING,
        thresholds={**DEFAULT_THRESHOLDS, **(payload.get("thresholds") or {})},
        environment=payload.get("environment") or {},
        summary=summarize_results([]),
    )


def upsert_result(run: PerformanceEvaluationRun, payload: dict) -> AssetPerformanceResult:
    asset_id = payload["asset_id"]
    try:
        asset = Asset.objects.select_related("target", "snapshot").get(id=asset_id)
    except Asset.DoesNotExist as exc:
        raise InvalidPerformanceResult("asset_id does not exist.", {"asset_id": asset_id}) from exc

    if asset.snapshot_id != run.snapshot_id:
        raise InvalidPerformanceResult(
            "asset does not belong to the performance run snapshot.",
            {"asset_id": asset.id, "asset_snapshot_id": asset.snapshot_id, "run_snapshot_id": run.snapshot_id},
        )

    compatibility_status = payload.get("compatibility_status", "PASS")
    baseline_metrics = _baseline_metrics_for(run, asset)
    evaluation = evaluate_asset_performance(
        metrics=payload.get("metrics") or {},
        baseline_metrics=baseline_metrics,
        compatibility_status=compatibility_status,
        thresholds=run.thresholds,
    )
    status = "ERROR" if compatibility_status == "ERROR" else evaluation["status"]
    recommendation = payload.get("recommendation") or evaluation["recommendation"]
    measured_at = timezone.now()

    result, _created = AssetPerformanceResult.objects.update_or_create(
        run=run,
        asset=asset,
        defaults={
            "status": status,
            "compatibility_status": compatibility_status,
            "negotiated_algorithm": payload.get("negotiated_algorithm", ""),
            "metrics": payload.get("metrics") or {},
            "deltas": evaluation["deltas"],
            "signals": evaluation["signals"],
            "recommendation": recommendation,
            "error_message": payload.get("error_message", ""),
            "measured_at": measured_at,
        },
    )

    if run.status == "PENDING":
        run.status = "RUNNING"
        run.started_at = run.started_at or timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])
    refresh_run_summary(run)
    return result


def update_run_status(run: PerformanceEvaluationRun, status: str, summary: dict | None = None) -> PerformanceEvaluationRun:
    run.status = status
    if status == "RUNNING":
        run.started_at = run.started_at or timezone.now()
    if status in {"COMPLETED", "FAILED"}:
        run.completed_at = run.completed_at or timezone.now()
    if summary is not None:
        run.summary = {**run.summary, **summary}
    run.save(update_fields=["status", "started_at", "completed_at", "summary", "updated_at"])
    return run


def refresh_run_summary(run: PerformanceEvaluationRun) -> dict:
    results = [
        {"status": result.status, "deltas": result.deltas}
        for result in run.results.all()
    ]
    run.summary = summarize_results(results)
    run.save(update_fields=["summary", "updated_at"])
    return run.summary


def serialize_run(run: PerformanceEvaluationRun) -> dict:
    return {
        "id": run.id,
        "snapshot_id": run.snapshot_id,
        "baseline_snapshot_id": run.baseline_snapshot_id,
        "trigger": run.trigger,
        "profile": run.profile,
        "status": run.status,
        "thresholds": run.thresholds,
        "environment": run.environment,
        "summary": run.summary,
        "started_at": job_services.serialize_dt(run.started_at),
        "completed_at": job_services.serialize_dt(run.completed_at),
        "created_at": job_services.serialize_dt(run.created_at),
    }


def serialize_result(result: AssetPerformanceResult) -> dict:
    target_label = None
    if result.asset.target:
        target_label = f"{result.asset.target.host}:{result.asset.target.port}"
    return {
        "id": result.id,
        "run_id": result.run_id,
        "asset_id": result.asset_id,
        "asset_name": result.asset.name,
        "bom_ref": result.asset.bom_ref,
        "target_label": target_label,
        "status": result.status,
        "compatibility_status": result.compatibility_status,
        "negotiated_algorithm": result.negotiated_algorithm,
        "metrics": result.metrics,
        "deltas": result.deltas,
        "signals": result.signals,
        "recommendation": result.recommendation,
        "error_message": result.error_message,
        "measured_at": job_services.serialize_dt(result.measured_at),
    }


def serialize_run_detail(run: PerformanceEvaluationRun) -> dict:
    return {
        **serialize_run(run),
        "results": [
            serialize_result(result)
            for result in run.results.select_related("asset", "asset__target").order_by("asset__bom_ref", "id")
        ],
    }


def _baseline_metrics_for(run: PerformanceEvaluationRun, asset: Asset) -> dict | None:
    if not run.baseline_snapshot_id:
        return None
    baseline_asset = Asset.objects.filter(snapshot_id=run.baseline_snapshot_id, bom_ref=asset.bom_ref).first()
    if not baseline_asset:
        return None
    baseline_run = (
        PerformanceEvaluationRun.objects.filter(snapshot_id=run.baseline_snapshot_id, profile=run.profile)
        .exclude(id=run.id)
        .order_by("-created_at")
        .first()
    )
    if not baseline_run:
        return None
    baseline_result = AssetPerformanceResult.objects.filter(run=baseline_run, asset=baseline_asset).order_by("-measured_at").first()
    return baseline_result.metrics if baseline_result else None
