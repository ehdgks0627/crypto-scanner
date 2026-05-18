from typing import Literal

from django.db import transaction
from ninja import Router
from pydantic import Field

from apps.assets import services
from apps.assets.models import Asset, AssetContextOverride
from apps.core.errors import error_response
from apps.core.schemas import StrictSchema


router = Router(tags=["Assets"])


class AssetContextPatch(StrictSchema):
    sensitivity: Literal["low", "medium", "high", "critical"] | None = None
    lifespan_years: int | None = Field(default=None, ge=0)
    criticality: Literal["low", "medium", "high", "critical"] | None = None
    exposure: Literal["public_internet", "dmz", "internal_network", "air_gapped"] | None = None
    service_role: str | None = None


@router.get("/assets/{asset_id}")
def get_asset(request, asset_id: int):
    try:
        asset = Asset.objects.select_related("target").get(id=asset_id)
    except Asset.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return services.serialize_asset_detail(asset)


@router.patch("/assets/{asset_id}/context")
def patch_asset_context(request, asset_id: int, payload: AssetContextPatch):
    try:
        asset = Asset.objects.select_related("target").get(id=asset_id)
    except Asset.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)

    patch = payload.model_dump(exclude_unset=True)
    try:
        with transaction.atomic():
            override, _created = AssetContextOverride.objects.get_or_create(asset=asset)
            keys = set(override.override_keys)
            for field, value in patch.items():
                setattr(override, field, value)
                if value is None:
                    keys.discard(field)
                else:
                    keys.add(field)
            override.override_keys = sorted(keys)
            override.save()
            async_job = services.create_recompute_job(asset.id)
    except services.EnqueueUnavailable:
        return error_response("service_unavailable", "Worker queue is unavailable.", status=503)

    asset.refresh_from_db()
    override.refresh_from_db()
    return {
        "asset_id": asset.id,
        "applied_overrides": patch,
        "effective_context": services.effective_context(asset, override),
        "context_override": services.override_to_dict(override),
        "context_sources": services.context_sources(asset, override),
        "recompute_job_id": async_job.id,
    }


@router.post("/assets/{asset_id}/context-suggestion")
def suggest_asset_context(request, asset_id: int):
    try:
        asset = Asset.objects.select_related("target").get(id=asset_id)
    except Asset.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    try:
        return services.suggest_asset_context(asset)
    except services.ContextSuggestionUnavailable as exc:
        return error_response(
            "service_unavailable",
            "AI recommendation provider is unavailable.",
            {"reason": str(exc)},
            status=503,
        )


@router.post("/assets/{asset_id}/qualitative")
def request_qualitative_assessment(request, asset_id: int):
    try:
        asset = Asset.objects.select_related("target").get(id=asset_id)
    except Asset.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    assessment = services.refresh_qualitative_assessment(asset)
    return services.serialize_qualitative(assessment)
