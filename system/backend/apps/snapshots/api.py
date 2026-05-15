import re
from typing import Literal

from django.db import transaction
from django.http import JsonResponse
from ninja import Query, Router
from pydantic import Field

from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema
from apps.jobs import services as job_services
from apps.risk import services as risk_services
from apps.risk.models import RiskScore
from apps.snapshots.cbom import build_cbom_document
from apps.snapshots.migration_plan import recommend_for_risk_score
from apps.snapshots.models import CbomSnapshot


router = Router(tags=["Snapshots"])

RiskSortParam = Literal["score", "-score", "computed_at", "-computed_at"]


class RiskWeightsPayload(StrictSchema):
    wA: float = Field(ge=0.5, le=2.0)
    wD: float = Field(ge=0.5, le=2.0)
    wE: float = Field(ge=0.5, le=2.0)
    wL: float = Field(ge=0.5, le=2.0)
    wC: float = Field(ge=0.5, le=2.0)


class RecomputePayload(StrictSchema):
    weights: RiskWeightsPayload
    persist_weights_as_default: bool = False


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
        build_cbom_document(snapshot),
        content_type="application/vnd.cyclonedx+json",
        headers={"Content-Disposition": f'attachment; filename="cbom-{snapshot.id}.json"'},
    )


@router.get("/snapshots/{snapshot_id}/diff")
def diff_snapshots(request, snapshot_id: int, other: int):
    try:
        snapshot_b = CbomSnapshot.objects.get(id=snapshot_id)
        snapshot_a = CbomSnapshot.objects.get(id=other)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)

    assets_a = {asset.bom_ref: asset for asset in snapshot_a.assets.all()}
    assets_b = {asset.bom_ref: asset for asset in snapshot_b.assets.all()}
    added_keys = set(assets_b) - set(assets_a)
    removed_keys = set(assets_a) - set(assets_b)
    shared_keys = set(assets_a) & set(assets_b)
    modified_keys = {key for key in shared_keys if _diff_field_changes(assets_a[key], assets_b[key])}
    unchanged_keys = shared_keys - modified_keys
    modified = [
        {**_diff_asset(assets_b[key]), "field_changes": _diff_field_changes(assets_a[key], assets_b[key])}
        for key in sorted(modified_keys)
    ]
    return {
        "snapshot_a": snapshot_a.id,
        "snapshot_b": snapshot_b.id,
        "added": [_diff_asset(assets_b[key]) for key in sorted(added_keys)],
        "removed": [_diff_asset(assets_a[key]) for key in sorted(removed_keys)],
        "modified": modified,
        "regressions": _diff_regressions(assets_a, assets_b, removed_keys, modified_keys),
        "unchanged_count": len(unchanged_keys),
    }


def _parse_csv(value: str | None):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _diff_asset(asset):
    return {
        "bom_ref": asset.bom_ref,
        "type": asset.asset_type,
        "name": asset.name,
    }


def _diff_field_changes(before, after):
    changes = {}
    for field in ("name", "asset_type", "algorithm", "algorithm_family"):
        before_value = getattr(before, field)
        after_value = getattr(after, field)
        if before_value != after_value:
            changes[field] = [before_value, after_value]
    return changes


def _diff_regressions(assets_a, assets_b, removed_keys, modified_keys):
    regressions = []
    for key in sorted(removed_keys):
        before = assets_a[key]
        regressions.append(
            {
                "kind": "asset_removed",
                "severity": "high",
                "bom_ref": before.bom_ref,
                "asset_type": before.asset_type,
                "message": "Asset is missing from the post-migration snapshot.",
                "before": _regression_asset_state(before),
                "after": None,
            }
        )

    for key in sorted(modified_keys):
        regression = _algorithm_regression(assets_a[key], assets_b[key])
        if regression:
            regressions.append(regression)
    return regressions


def _algorithm_regression(before, after):
    if before.algorithm and not after.algorithm:
        return {
            "kind": "algorithm_removed",
            "severity": "high",
            "bom_ref": before.bom_ref,
            "asset_type": before.asset_type,
            "message": "Algorithm metadata was removed from the post-migration snapshot.",
            "before": _regression_asset_state(before),
            "after": _regression_asset_state(after),
        }

    before_strength = _algorithm_strength(before)
    after_strength = _algorithm_strength(after)
    if before_strength[0] == 0 or after_strength[0] == 0:
        return None
    if after_strength >= before_strength:
        return None
    return {
        "kind": "algorithm_downgrade",
        "severity": "high",
        "bom_ref": after.bom_ref,
        "asset_type": after.asset_type,
        "message": "Algorithm strength decreased in the post-migration snapshot.",
        "before": _regression_asset_state(before),
        "after": _regression_asset_state(after),
    }


def _regression_asset_state(asset):
    return {
        "bom_ref": asset.bom_ref,
        "type": asset.asset_type,
        "name": asset.name,
        "algorithm": asset.algorithm,
        "algorithm_family": asset.algorithm_family,
    }


def _algorithm_strength(asset):
    family = _normalized_algorithm_family(asset.algorithm_family, asset.algorithm)
    family_rank = {
        "ML-KEM": 500,
        "ML-DSA": 500,
        "SLH-DSA": 500,
        "EDDSA": 360,
        "ECDSA": 340,
        "ECDH": 340,
        "X25519": 340,
        "RSA": 300,
        "DH": 200,
        "DSA": 150,
    }.get(family, 0)
    return family_rank, _algorithm_size(asset)


def _normalized_algorithm_family(family: str, algorithm: str) -> str:
    value = f"{family} {algorithm}".upper().replace("_", "-")
    if "ML-KEM" in value or "KYBER" in value:
        return "ML-KEM"
    if "ML-DSA" in value or "DILITHIUM" in value:
        return "ML-DSA"
    if "SLH-DSA" in value or "SPHINCS" in value:
        return "SLH-DSA"
    if "ED25519" in value or "ED448" in value or "EDDSA" in value:
        return "EDDSA"
    if "ECDSA" in value:
        return "ECDSA"
    if "ECDH" in value or "X25519" in value or "CURVE25519" in value:
        return "ECDH"
    if "RSA" in value:
        return "RSA"
    if "DIFFIE" in value or "MODP" in value or re.search(r"\bDH\b", value):
        return "DH"
    if re.search(r"\bDSA\b", value):
        return "DSA"
    return ""


def _algorithm_size(asset) -> int:
    metadata = asset.metadata or {}
    for key in ("key_size_bits", "key_size", "bits"):
        value = metadata.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    values = [int(match) for match in re.findall(r"\d+", f"{asset.algorithm} {asset.algorithm_family}")]
    return max(values) if values else 0


def _risk_for_asset(asset):
    return asset.risk_scores.order_by("-id").first()


def _is_quantum_vulnerable(asset):
    return asset.algorithm_family in {"RSA", "ECDSA", "ECDH", "DH"}


@router.get("/snapshots/{snapshot_id}/assets")
def list_snapshot_assets(
    request,
    snapshot_id: int,
    asset_class: str | None = None,
    asset_type: str | None = None,
    target_id: int | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    tier: str | None = None,
    quantum_vulnerable: bool | None = None,
    q: str | None = None,
    sort: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    from apps.assets import services as asset_services

    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    assets = list(snapshot.assets.select_related("target").prefetch_related("risk_scores"))
    asset_classes = set(_parse_csv(asset_class))
    if asset_classes:
        assets = [asset for asset in assets if asset.asset_class in asset_classes]
    if asset_type:
        asset_types = set(_parse_csv(asset_type))
        assets = [asset for asset in assets if asset.asset_type in asset_types]
    if target_id is not None:
        assets = [asset for asset in assets if asset.target_id == target_id]
    tiers = set(_parse_csv(tier))
    if tiers:
        assets = [asset for asset in assets if _risk_for_asset(asset) and _risk_for_asset(asset).tier in tiers]
    if min_score is not None:
        assets = [asset for asset in assets if _risk_for_asset(asset) and _risk_for_asset(asset).score >= min_score]
    if max_score is not None:
        assets = [asset for asset in assets if _risk_for_asset(asset) and _risk_for_asset(asset).score <= max_score]
    if quantum_vulnerable is not None:
        assets = [asset for asset in assets if _is_quantum_vulnerable(asset) is quantum_vulnerable]
    if q:
        query = q.casefold()
        assets = [
            asset
            for asset in assets
            if query in asset.name.casefold()
            or query in asset.bom_ref.casefold()
            or query in asset.algorithm.casefold()
            or (asset.target and query in asset.target.host.casefold())
        ]
    if sort == "-risk_score":
        assets.sort(key=lambda asset: (_risk_for_asset(asset).score if _risk_for_asset(asset) else 0), reverse=True)
    elif sort == "name":
        assets.sort(key=lambda asset: asset.name.casefold())
    elif sort == "-name":
        assets.sort(key=lambda asset: asset.name.casefold(), reverse=True)
    total = len(assets)
    items = [asset_services.serialize_asset_summary(asset, _risk_for_asset(asset)) for asset in assets[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}/risks")
def list_snapshot_risks(
    request,
    snapshot_id: int,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    sort: RiskSortParam | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)

    tiers = request.GET.getlist("tier")
    if len(tiers) > 1:
        return error_response(
            "validation_error",
            "Repeated query parameters are not supported.",
            {"parameter": "tier", "expected": "CSV"},
            status=400,
        )

    selected_tiers = tiers[0].split(",") if tiers and tiers[0] else []
    queryset = RiskScore.objects.filter(snapshot_id=snapshot_id).select_related("asset", "asset__target").order_by("-score")
    if selected_tiers:
        queryset = queryset.filter(tier__in=selected_tiers)
    if min_score is not None:
        queryset = queryset.filter(score__gte=min_score)
    if max_score is not None:
        queryset = queryset.filter(score__lte=max_score)
    if sort == "score":
        queryset = queryset.order_by("score")
    elif sort == "-score":
        queryset = queryset.order_by("-score")
    elif sort == "-computed_at":
        queryset = queryset.order_by("-computed_at")
    elif sort == "computed_at":
        queryset = queryset.order_by("computed_at")
    total = queryset.count()
    items = [risk_services.serialize_risk_score(score) for score in queryset[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}/risks/top")
def list_top_snapshot_risks(request, snapshot_id: int, n: int = Query(10, ge=1, le=100)):
    if not CbomSnapshot.objects.filter(id=snapshot_id).exists():
        return error_response("not_found", "Resource not found.", status=404)
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
def get_migration_plan(
    request,
    snapshot_id: int,
    min_score: int | None = Query(None, ge=0, le=100),
    tier: str | None = None,
    asset_type: str | None = None,
    target_id: int | None = None,
    asset_ids: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)

    tiers = set(_parse_csv(tier))
    queryset = RiskScore.objects.filter(snapshot_id=snapshot_id).select_related("asset", "asset__target").order_by("-score")
    if min_score is not None:
        queryset = queryset.filter(score__gte=min_score)
    if tiers:
        queryset = queryset.filter(tier__in=tiers)
    if asset_type:
        queryset = queryset.filter(asset__asset_type__in=_parse_csv(asset_type))
    if target_id is not None:
        queryset = queryset.filter(asset__target_id=target_id)
    if asset_ids:
        try:
            selected_asset_ids = [int(value) for value in _parse_csv(asset_ids)]
        except ValueError:
            return error_response("unprocessable", "asset_ids must be CSV integers.", {"parameter": "asset_ids"}, status=422)
        queryset = queryset.filter(asset_id__in=selected_asset_ids)

    total = queryset.count()
    items = []
    for risk_score in queryset[offset : offset + limit]:
        items.append(recommend_for_risk_score(risk_score))
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.get("/snapshots/{snapshot_id}/migration-plan/impact")
def get_migration_impact(request, snapshot_id: int, asset_ids: str = ""):
    if not asset_ids:
        return error_response("unprocessable", "asset_ids is required.", {"parameter": "asset_ids"}, status=422)
    try:
        ids = [int(value) for value in asset_ids.split(",") if value]
    except ValueError:
        return error_response("unprocessable", "asset_ids must be CSV integers.", {"parameter": "asset_ids"}, status=422)
    try:
        snapshot = CbomSnapshot.objects.get(id=snapshot_id)
    except CbomSnapshot.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    assets = list(snapshot.assets.select_related("target").filter(id__in=ids))
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
    hosts = sorted({asset.target.host for asset in assets if asset.target})
    services = sorted({f"{asset.target.host}:{asset.target.port}" for asset in assets if asset.target})
    return {
        "selected_count": count,
        "hosts": hosts,
        "services": services,
        "cert_reissues": count,
        "config_changes": count,
        "key_regens": count,
        "estimated_downtime_min": count * 15,
    }
