from __future__ import annotations

from django.utils import timezone

from apps.assets.models import Asset
from apps.jobs import services as job_services
from apps.performance.models import AssetPerformanceResult, PerformanceEvaluationRun
from apps.snapshots.models import CbomSnapshot
from performance_engine import DEFAULT_THRESHOLDS, evaluate_asset_performance, normalize_availability_metrics, summarize_results


class InvalidPerformanceResult(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def create_run(snapshot: CbomSnapshot, payload: dict) -> PerformanceEvaluationRun:
    trigger = payload.get("trigger", "manual")
    baseline_snapshot = _resolve_baseline_snapshot(snapshot, payload.get("baseline_snapshot_id"), trigger)

    run = PerformanceEvaluationRun.objects.create(
        snapshot=snapshot,
        baseline_snapshot=baseline_snapshot,
        trigger=trigger,
        profile=payload.get("profile", "smoke"),
        status=PerformanceEvaluationRun.PENDING,
        thresholds={**DEFAULT_THRESHOLDS, **(payload.get("thresholds") or {})},
        environment=payload.get("environment") or {},
        summary=summarize_results([]),
    )
    if trigger == "post_migration":
        _link_post_migration_snapshot(run)
    return run


def _resolve_baseline_snapshot(snapshot: CbomSnapshot, baseline_snapshot_id: int | None, trigger: str) -> CbomSnapshot | None:
    if baseline_snapshot_id is not None:
        baseline_snapshot = CbomSnapshot.objects.filter(id=baseline_snapshot_id).first()
        if baseline_snapshot is None:
            raise InvalidPerformanceResult("baseline_snapshot_id does not exist.", {"baseline_snapshot_id": baseline_snapshot_id})
        if baseline_snapshot.id == snapshot.id:
            raise InvalidPerformanceResult("baseline_snapshot_id must be different from snapshot_id.", {"baseline_snapshot_id": baseline_snapshot_id})
        if trigger == "post_migration" and baseline_snapshot.id > snapshot.id:
            raise InvalidPerformanceResult(
                "baseline_snapshot_id must reference a pre-migration snapshot.",
                {"baseline_snapshot_id": baseline_snapshot_id, "snapshot_id": snapshot.id},
            )
        return baseline_snapshot

    if trigger != "post_migration":
        return None

    baseline_snapshot = CbomSnapshot.objects.filter(id__lt=snapshot.id).order_by("-id").first()
    if baseline_snapshot is None:
        raise InvalidPerformanceResult(
            "post_migration performance runs require a pre-migration snapshot.",
            {"snapshot_id": snapshot.id},
        )
    return baseline_snapshot


def _link_post_migration_snapshot(run: PerformanceEvaluationRun) -> None:
    summary = dict(run.snapshot.summary or {})
    migration = dict(summary.get("migration") or {})
    post_migration_runs = [
        item
        for item in migration.get("post_migration_runs", [])
        if isinstance(item, dict) and item.get("run_id") != run.id
    ]
    post_migration_runs.append(
        {
            "run_id": run.id,
            "profile": run.profile,
            "baseline_snapshot_id": run.baseline_snapshot_id,
            "post_migration_snapshot_id": run.snapshot_id,
        }
    )
    migration.update(
        {
            "phase": "post_migration",
            "pre_migration_snapshot_id": run.baseline_snapshot_id,
            "post_migration_snapshot_id": run.snapshot_id,
            "latest_performance_run_id": run.id,
            "latest_profile": run.profile,
            "post_migration_runs": post_migration_runs,
        }
    )
    summary["migration"] = migration
    run.snapshot.summary = summary
    run.snapshot.save(update_fields=["summary", "updated_at"])


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
    metrics = normalize_availability_metrics(_metrics_with_protocol(asset, payload.get("metrics") or {}))
    baseline_metrics = _baseline_metrics_for(run, asset)
    if baseline_metrics:
        metrics["baseline_metrics"] = normalize_availability_metrics(baseline_metrics)
    evaluation = evaluate_asset_performance(
        metrics=metrics,
        baseline_metrics=baseline_metrics,
        compatibility_status=compatibility_status,
        thresholds=run.thresholds,
    )
    status = "ERROR" if compatibility_status == "ERROR" else evaluation["status"]
    recommendation = payload.get("recommendation") or evaluation["recommendation"]
    metrics = _metrics_with_failure_context(metrics, payload, evaluation, status)
    measured_at = timezone.now()

    result, _created = AssetPerformanceResult.objects.update_or_create(
        run=run,
        asset=asset,
        defaults={
            "status": status,
            "compatibility_status": compatibility_status,
            "negotiated_algorithm": payload.get("negotiated_algorithm", ""),
            "metrics": metrics,
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
        {"status": result.status, "deltas": result.deltas, "metrics": result.metrics, "bom_ref": result.asset.bom_ref}
        for result in run.results.select_related("asset").all()
    ]
    run.summary = summarize_results(results)
    run.save(update_fields=["summary", "updated_at"])
    return run.summary


def serialize_run(run: PerformanceEvaluationRun) -> dict:
    return {
        "id": run.id,
        "snapshot_id": run.snapshot_id,
        "baseline_snapshot_id": run.baseline_snapshot_id,
        "post_migration_snapshot_id": run.snapshot_id if run.trigger == "post_migration" else None,
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
    protocol = _result_protocol(result)
    response_code = result.metrics.get("response_code")
    failure_reason = _result_failure_reason(result)
    return {
        "id": result.id,
        "run_id": result.run_id,
        "asset_id": result.asset_id,
        "asset_name": result.asset.name,
        "bom_ref": result.asset.bom_ref,
        "target_label": target_label,
        "protocol": protocol,
        "response_code": str(response_code) if response_code is not None else None,
        "failure_reason": failure_reason,
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


def _metrics_with_protocol(asset: Asset, metrics: dict) -> dict:
    enriched = dict(metrics)
    if not enriched.get("protocol"):
        enriched["protocol"] = _asset_protocol(asset)
    return enriched


def _result_protocol(result: AssetPerformanceResult) -> str:
    return str(result.metrics.get("protocol") or _asset_protocol(result.asset)).upper()


def _metrics_with_failure_context(metrics: dict, payload: dict, evaluation: dict, status: str) -> dict:
    enriched = dict(metrics)
    if status in {"WARN", "FAIL", "ERROR"} and not enriched.get("failure_reason"):
        if payload.get("error_message"):
            enriched["failure_reason"] = str(payload["error_message"])
        elif evaluation.get("signals"):
            enriched["failure_reason"] = str(evaluation["signals"][0].get("reason") or status)
    return normalize_availability_metrics(enriched)


def _result_failure_reason(result: AssetPerformanceResult) -> str | None:
    failure_reason = result.metrics.get("failure_reason")
    if failure_reason:
        return str(failure_reason)
    if result.error_message:
        return result.error_message
    if result.signals:
        return str(result.signals[0].get("reason") or "")
    return None


def _asset_protocol(asset: Asset) -> str:
    if asset.target and asset.target.protocol_hint:
        return asset.target.protocol_hint
    metadata = asset.metadata or {}
    if metadata.get("protocol"):
        return str(metadata["protocol"])
    if asset.asset_type in {"ssh_host_key", "ssh_user_key"} or "ssh" in asset.bom_ref.lower():
        return "SSH"
    return "UNKNOWN"
