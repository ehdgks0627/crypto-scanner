from typing import Literal

from django.http import JsonResponse
from ninja import Query, Router
from pydantic import Field

from apps.core.errors import error_response
from apps.core.pagination import page_envelope
from apps.core.schemas import StrictSchema
from apps.performance import services
from apps.performance.models import PerformanceEvaluationRun
from apps.snapshots.models import CbomSnapshot


router = Router(tags=["Performance"])

RunTrigger = Literal["manual", "post_migration", "scheduled", "canary"]
RunProfile = Literal["smoke", "baseline", "canary", "stress"]
RunStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
ResultStatus = Literal["PASS", "WARN", "FAIL", "ERROR"]


class PerformanceRunCreate(StrictSchema):
    baseline_snapshot_id: int | None = None
    trigger: RunTrigger = "manual"
    profile: RunProfile = "smoke"
    thresholds: dict[str, float] = Field(default_factory=dict)
    environment: dict[str, object] = Field(default_factory=dict)


class PerformanceRunPatch(StrictSchema):
    status: RunStatus
    summary: dict[str, object] | None = None


class PerformanceResultCreate(StrictSchema):
    asset_id: int
    compatibility_status: ResultStatus = "PASS"
    negotiated_algorithm: str = ""
    metrics: dict[str, object] = Field(default_factory=dict)
    recommendation: str | None = None
    error_message: str = ""


@router.get("/snapshots/{snapshot_id}/performance-runs")
def list_performance_runs(
    request,
    snapshot_id: int,
    profile: RunProfile | None = None,
    status: RunStatus | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    if not CbomSnapshot.objects.filter(id=snapshot_id).exists():
        return error_response("not_found", "Resource not found.", status=404)
    queryset = PerformanceEvaluationRun.objects.filter(snapshot_id=snapshot_id).order_by("-created_at")
    if profile:
        queryset = queryset.filter(profile=profile)
    if status:
        queryset = queryset.filter(status=status)
    total = queryset.count()
    items = [services.serialize_run(run) for run in queryset[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/snapshots/{snapshot_id}/performance-runs")
def create_performance_run(request, snapshot_id: int, payload: PerformanceRunCreate):
    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    try:
        run = services.create_run(snapshot, payload.model_dump())
    except services.InvalidPerformanceResult as exc:
        return error_response("unprocessable", exc.message, exc.details, status=422)
    return JsonResponse(services.serialize_run(run), status=201)


@router.get("/snapshots/{snapshot_id}/performance-runs/{run_id}")
def get_performance_run(request, snapshot_id: int, run_id: int):
    try:
        run = PerformanceEvaluationRun.objects.get(id=run_id, snapshot_id=snapshot_id)
    except PerformanceEvaluationRun.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return services.serialize_run_detail(run)


@router.patch("/snapshots/{snapshot_id}/performance-runs/{run_id}")
def patch_performance_run(request, snapshot_id: int, run_id: int, payload: PerformanceRunPatch):
    try:
        run = PerformanceEvaluationRun.objects.get(id=run_id, snapshot_id=snapshot_id)
    except PerformanceEvaluationRun.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return services.serialize_run(services.update_run_status(run, payload.status, payload.summary))


@router.post("/snapshots/{snapshot_id}/performance-runs/{run_id}/results")
def upsert_performance_result(request, snapshot_id: int, run_id: int, payload: PerformanceResultCreate):
    try:
        run = PerformanceEvaluationRun.objects.get(id=run_id, snapshot_id=snapshot_id)
    except PerformanceEvaluationRun.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    try:
        result = services.upsert_result(run, payload.model_dump())
    except services.InvalidPerformanceResult as exc:
        return error_response("unprocessable", exc.message, exc.details, status=422)
    return JsonResponse(services.serialize_result(result), status=201)


@router.get("/assets/{asset_id}/performance-history")
def list_asset_performance_history(
    request,
    asset_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    from apps.assets.models import Asset
    from apps.performance.models import AssetPerformanceResult

    if not Asset.objects.filter(id=asset_id).exists():
        return error_response("not_found", "Resource not found.", status=404)
    queryset = AssetPerformanceResult.objects.filter(asset_id=asset_id).select_related("asset", "asset__target").order_by("-measured_at")
    total = queryset.count()
    items = [services.serialize_result(result) for result in queryset[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)
