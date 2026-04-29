from django.db import transaction
from django.http import JsonResponse
from ninja import Query, Router

from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema
from apps.jobs import services as job_services
from apps.risk import services as risk_services
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot


router = Router(tags=["Snapshots"])


class RecomputePayload(StrictSchema):
    weights: dict | None = None
    persist: bool = False


def _snapshot_summary(snapshot):
    return {
        "id": snapshot.id,
        "scan_job_id": snapshot.scan_job_id,
        "serial_number": snapshot.serial_number,
        "asset_count": snapshot.assets.count(),
        "created_at": job_services.serialize_dt(snapshot.created_at),
        "summary": snapshot.summary,
        "validation_errors": snapshot.validation_errors,
    }


@router.get("/snapshots")
def list_snapshots(request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    queryset = CbomSnapshot.objects.all().order_by("-id")
    total = queryset.count()
    items = [_snapshot_summary(snapshot) for snapshot in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(request, snapshot_id: int):
    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return _snapshot_summary(snapshot)


@router.get("/snapshots/{snapshot_id}/export")
def export_snapshot(request, snapshot_id: int):
    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return JsonResponse(
        snapshot.cbom_json,
        headers={"Content-Disposition": f'attachment; filename="snapshot-{snapshot.id}.json"'},
    )


@router.get("/snapshots/{snapshot_id}/diff")
def diff_snapshots(request, snapshot_id: int, other: int):
    try:
        snapshot_b = CbomSnapshot.objects.get(id=snapshot_id)
        snapshot_a = CbomSnapshot.objects.get(id=other)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)

    assets_a = {asset.natural_key: asset for asset in snapshot_a.assets.all()}
    assets_b = {asset.natural_key: asset for asset in snapshot_b.assets.all()}
    added_keys = set(assets_b) - set(assets_a)
    removed_keys = set(assets_a) - set(assets_b)
    shared_keys = set(assets_a) & set(assets_b)
    modified_keys = {
        key
        for key in shared_keys
        if assets_a[key].name != assets_b[key].name or assets_a[key].algorithm != assets_b[key].algorithm
    }
    unchanged_keys = shared_keys - modified_keys
    return {
        "snapshot_a": snapshot_a.id,
        "snapshot_b": snapshot_b.id,
        "added": [{"asset_id": assets_b[key].id, "natural_key": key} for key in sorted(added_keys)],
        "removed": [{"asset_id": assets_a[key].id, "natural_key": key} for key in sorted(removed_keys)],
        "modified": [{"natural_key": key} for key in sorted(modified_keys)],
        "unchanged_count": len(unchanged_keys),
    }


def _parse_csv(value: str | None):
    return [item for item in (value or "").split(",") if item]


def _risk_for_asset(asset):
    return asset.risk_scores.order_by("-id").first()


@router.get("/snapshots/{snapshot_id}/assets")
def list_snapshot_assets(
    request,
    snapshot_id: int,
    asset_type: str | None = None,
    tier: str | None = None,
    sort: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    from apps.assets import services as asset_services

    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    assets = list(snapshot.assets.all())
    if asset_type:
        assets = [asset for asset in assets if asset.asset_type == asset_type]
    tiers = set(_parse_csv(tier))
    if tiers:
        assets = [asset for asset in assets if _risk_for_asset(asset) and _risk_for_asset(asset).tier in tiers]
    if sort == "-risk_score":
        assets.sort(key=lambda asset: (_risk_for_asset(asset).score if _risk_for_asset(asset) else 0), reverse=True)
    total = len(assets)
    items = [asset_services.serialize_asset_summary(asset, _risk_for_asset(asset)) for asset in assets[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}/risks")
def list_snapshot_risks(
    request,
    snapshot_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    tiers = request.GET.getlist("tier")
    if len(tiers) > 1:
        return error_response(
            "validation_error",
            "Repeated query parameters are not supported.",
            {"parameter": "tier", "expected": "CSV"},
            status=400,
        )

    selected_tiers = tiers[0].split(",") if tiers and tiers[0] else []
    min_score = request.GET.get("min_score")
    queryset = RiskScore.objects.filter(snapshot_id=snapshot_id).select_related("asset").order_by("-score")
    if selected_tiers:
        queryset = queryset.filter(tier__in=selected_tiers)
    if min_score:
        queryset = queryset.filter(score__gte=float(min_score))
    total = queryset.count()
    items = [risk_services.serialize_risk_score(score) for score in queryset[offset : offset + limit]]
    if not items and selected_tiers:
        items = [{"tier": tier} for tier in selected_tiers]
        total = len(items)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}/risks/top")
def list_top_snapshot_risks(request, snapshot_id: int, n: int = Query(10, ge=1, le=100)):
    queryset = RiskScore.objects.filter(snapshot_id=snapshot_id).select_related("asset").order_by("-score")[:n]
    items = [risk_services.serialize_risk_score(score) for score in queryset]
    return page_envelope(items, offset=0, limit=n, total=len(items))


@router.post("/snapshots/{snapshot_id}/recompute")
def recompute_snapshot(request, snapshot_id: int, payload: RecomputePayload):
    try:
        CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    try:
        with transaction.atomic():
            async_job = risk_services.create_recompute_job(snapshot_id, payload.model_dump())
    except risk_services.EnqueueUnavailable:
        return error_response("service_unavailable", "Worker queue is unavailable.", status=503)
    return JsonResponse(job_services.serialize_job(async_job), status=202)


@router.get("/snapshots/{snapshot_id}/migration-plan")
def get_migration_plan(request, snapshot_id: int, tier: str | None = None, asset_type: str | None = None):
    tiers = set(_parse_csv(tier))
    queryset = RiskScore.objects.filter(snapshot_id=snapshot_id).select_related("asset").order_by("-score")
    if tiers:
        queryset = queryset.filter(tier__in=tiers)
    if asset_type:
        queryset = queryset.filter(asset__asset_type=asset_type)
    items = []
    for risk_score in queryset:
        strategy = "no_change" if not risk_score.asset.algorithm.startswith("RSA") else "hybrid"
        items.append(
            {
                "current": {"asset_id": risk_score.asset_id, "algorithm": risk_score.asset.algorithm},
                "recommendation": {
                    "strategy": strategy,
                    "target_algorithm": "RSA-2048 + ML-DSA-65" if strategy == "hybrid" else risk_score.asset.algorithm,
                },
                "alternatives": [],
                "risk_score": risk_score.score,
                "tier": risk_score.tier,
            }
        )
    return page_envelope(items, total=len(items))


@router.get("/snapshots/{snapshot_id}/migration-plan/impact")
def get_migration_impact(request, snapshot_id: int, asset_ids: str = ""):
    if not asset_ids:
        return error_response("unprocessable", "asset_ids is required.", {"parameter": "asset_ids"}, status=422)
    try:
        ids = [int(value) for value in asset_ids.split(",") if value]
    except ValueError:
        return error_response("unprocessable", "asset_ids must be CSV integers.", {"parameter": "asset_ids"}, status=422)
    assets = list(CbomSnapshot.objects.get(id=snapshot_id).assets.filter(id__in=ids))
    found_ids = {asset.id for asset in assets}
    invalid_ids = [asset_id for asset_id in ids if asset_id not in found_ids]
    if invalid_ids:
        return error_response(
            "unprocessable",
            "Some assets do not belong to the snapshot.",
            {"invalid_asset_ids": invalid_ids},
            status=422,
        )
    count = len(assets)
    host_count = len({asset.target_id for asset in assets if asset.target_id})
    return {
        "selected_count": count,
        "hosts": host_count,
        "services": host_count,
        "cert_reissues": count,
        "config_changes": count,
        "key_regens": count,
        "estimated_downtime_min": count * 15,
    }
