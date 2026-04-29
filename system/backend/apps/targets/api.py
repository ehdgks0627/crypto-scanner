from typing import Literal

from datetime import UTC

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from ninja import Query, Router
from pydantic import AnyUrl, Field, IPvAnyAddress

from apps.core.errors import error_response
from apps.core.pagination import empty_page
from apps.core.schemas import StrictSchema
from apps.jobs.models import AsyncJob
from apps.targets import services
from apps.targets.models import Target, default_context


router = Router(tags=["Targets"])


class TargetContextPayload(StrictSchema):
    sensitivity: Literal["low", "medium", "high", "critical"] | None = None
    lifespan_years: int | None = Field(default=None, ge=0)
    criticality: Literal["low", "medium", "high", "critical"] | None = None
    exposure: Literal["public_internet", "dmz", "internal_network", "air_gapped"] | None = None
    service_role: str | None = None


class TargetCreatePayload(StrictSchema):
    host: str = Field(max_length=253)
    ip: IPvAnyAddress | None = None
    port: int = Field(ge=1, le=65535)
    protocol_hint: Literal["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]
    sni: str | None = Field(default=None, max_length=253)
    transport: Literal["TCP", "UDP"] = "TCP"
    agent_enabled: bool = False
    agent_url: AnyUrl | None = None
    context: TargetContextPayload | None = None


class TargetPatchPayload(StrictSchema):
    host: str | None = Field(default=None, max_length=253)
    ip: IPvAnyAddress | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol_hint: Literal["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"] | None = None
    sni: str | None = Field(default=None, max_length=253)
    transport: Literal["TCP", "UDP"] | None = None
    agent_enabled: bool | None = None
    agent_url: AnyUrl | None = None
    context: TargetContextPayload | None = None


def _schema_dict(schema, *, exclude_unset: bool = False):
    return schema.model_dump(exclude_unset=exclude_unset, mode="json")


def _normalized_context(context: dict | None):
    return {**default_context(), **(context or {})}


def _serialize_target(target: Target):
    return {
        "id": target.id,
        "host": target.host,
        "ip": target.ip,
        "port": target.port,
        "protocol_hint": target.protocol_hint,
        "sni": target.sni,
        "transport": target.transport,
        "agent_enabled": target.agent_enabled,
        "agent_url": target.agent_url,
        "context": _normalized_context(target.context),
        "created_at": target.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "updated_at": target.updated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def _not_found():
    return error_response("not_found", "Resource not found.", status=404)


@router.get("/targets")
def list_targets(
    request,
    host: str | None = None,
    protocol_hint: str | None = None,
    agent_enabled: bool | None = None,
    sort: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    queryset = Target.objects.all()
    if host:
        queryset = queryset.filter(host__icontains=host)
    if protocol_hint:
        queryset = queryset.filter(protocol_hint=protocol_hint)
    if agent_enabled is not None:
        queryset = queryset.filter(agent_enabled=agent_enabled)

    ordering = sort or "id"
    allowed_sort_fields = {"id", "host", "created_at", "updated_at"}
    sort_field = ordering.removeprefix("-")
    if sort_field not in allowed_sort_fields:
        return error_response(
            "validation_error",
            "Unsupported sort field.",
            {"parameter": "sort", "allowed": sorted(allowed_sort_fields)},
            status=400,
        )

    total = queryset.count()
    items = [
        _serialize_target(target)
        for target in queryset.order_by(ordering)[offset : offset + limit]
    ]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.post("/targets")
def create_target(request, payload: TargetCreatePayload):
    data = _schema_dict(payload)
    context_payload = data.pop("context", None)
    data["context"] = _normalized_context(context_payload)
    try:
        target = Target.objects.create(**data)
    except IntegrityError:
        return error_response(
            "conflict",
            "Target already exists.",
            {"fields": ["host", "port", "transport"]},
            status=409,
        )
    return JsonResponse(_serialize_target(target), status=201)


@router.get("/targets/{target_id}")
def get_target(request, target_id: int):
    try:
        target = Target.objects.get(id=target_id)
    except Target.DoesNotExist:
        return _not_found()
    return _serialize_target(target)


@router.patch("/targets/{target_id}")
def patch_target(request, target_id: int, payload: TargetPatchPayload):
    try:
        target = Target.objects.get(id=target_id)
    except Target.DoesNotExist:
        return _not_found()

    data = _schema_dict(payload, exclude_unset=True)
    context_patch = data.pop("context", None)
    context_changed = False

    for field, value in data.items():
        if getattr(target, field) != value:
            setattr(target, field, value)

    if context_patch is not None:
        previous_context = _normalized_context(target.context)
        next_context = {**previous_context, **context_patch}
        context_changed = next_context != previous_context
        target.context = next_context

    if not data and not context_changed:
        return {"target": _serialize_target(target), "recompute_job_id": None}

    try:
        with transaction.atomic():
            target.save()
            recompute_job_id = None
            if context_changed:
                async_job = AsyncJob.objects.create(
                    kind="recompute",
                    status=AsyncJob.PENDING,
                    request_payload={
                        "target_id": target.id,
                        "reason": "target_context_changed",
                    },
                )
                async_job.resource_id = async_job.id
                async_job.save(update_fields=["resource_id"])
                services.enqueue_target_recompute(async_job)
                recompute_job_id = async_job.id
    except services.EnqueueUnavailable:
        return error_response(
            "service_unavailable",
            "Worker queue is unavailable.",
            status=503,
        )

    target.refresh_from_db()
    return {"target": _serialize_target(target), "recompute_job_id": recompute_job_id}


@router.delete("/targets/{target_id}")
def delete_target(request, target_id: int):
    try:
        target = Target.objects.get(id=target_id)
    except Target.DoesNotExist:
        return _not_found()
    target.delete()
    return HttpResponse(status=204)
