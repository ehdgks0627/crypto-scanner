from django.db import transaction
from django.http import JsonResponse
from ninja import Router

from apps.assets.models import Asset
from apps.discoveries.models import DiscoveredEndpoint
from apps.jobs.models import AsyncJob, QueuedTask, ScanRunLog, ScanJob
from apps.performance.models import AssetPerformanceResult, PerformanceEvaluationRun
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


router = Router(tags=["Settings"])


@router.delete("/settings/snapshots")
def delete_snapshot_results(request):
    snapshot_ids = list(CbomSnapshot.objects.values_list("id", flat=True))
    job_ids = list(AsyncJob.objects.filter(kind__in=["scan_job", "recompute"]).values_list("id", flat=True))
    deleted = {
        "snapshots": len(snapshot_ids),
        "assets": Asset.objects.filter(snapshot_id__in=snapshot_ids).count(),
        "risk_scores": RiskScore.objects.filter(snapshot_id__in=snapshot_ids).count(),
        "performance_runs": PerformanceEvaluationRun.objects.filter(snapshot_id__in=snapshot_ids).count(),
        "performance_results": AssetPerformanceResult.objects.filter(run__snapshot_id__in=snapshot_ids).count(),
        "jobs": len(job_ids),
        "scan_jobs": ScanJob.objects.filter(async_job_id__in=job_ids).count(),
        "scan_logs": ScanRunLog.objects.filter(async_job_id__in=job_ids).count(),
        "queued_tasks": QueuedTask.objects.filter(async_job_id__in=job_ids).count(),
    }

    with transaction.atomic():
        CbomSnapshot.objects.filter(id__in=snapshot_ids).delete()
        AsyncJob.objects.filter(id__in=job_ids).delete()

    return JsonResponse({"deleted": deleted})


@router.delete("/settings/scan-targets")
def delete_scan_targets(request):
    deleted = {
        "scan_targets": Target.objects.count(),
        "discovery_endpoint_links": DiscoveredEndpoint.objects.filter(target__isnull=False).count(),
    }

    with transaction.atomic():
        Target.objects.all().delete()
        DiscoveredEndpoint.objects.filter(target__isnull=True, promoted=True).update(promoted=False)

    return JsonResponse({"deleted": deleted})
