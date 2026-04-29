from django.db import transaction
from django.http import JsonResponse
from ninja import Query, Router

from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema
from apps.discoveries import services
from apps.discoveries.models import DiscoveredEndpoint, Discovery
from apps.jobs.models import AsyncJob
from apps.targets.models import Target, default_context


router = Router(tags=["Discoveries"])


class DiscoveryCreate(StrictSchema):
    cidr: str
    ports: list[int] | None = None
    include_default_ports: bool = False


class PromotePayload(StrictSchema):
    endpoint_ids: list[int]
    target_overrides: dict | None = None


@router.get("/discoveries")
def list_discoveries(
    request,
    status: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    queryset = Discovery.objects.all().order_by("-id")
    if status:
        queryset = queryset.filter(status=status)
    total = queryset.count()
    items = [services.serialize_discovery(discovery) for discovery in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/discoveries")
def create_discovery(request, payload: DiscoveryCreate):
    try:
        with transaction.atomic():
            async_job = AsyncJob.objects.create(
                kind="discovery",
                status=AsyncJob.PENDING,
                request_payload=payload.model_dump(),
            )
            discovery = Discovery.objects.create(
                async_job=async_job,
                cidr=payload.cidr,
                ports=payload.ports or [],
                include_default_ports=payload.include_default_ports,
                status=async_job.status,
            )
            async_job.resource_id = discovery.id
            async_job.save(update_fields=["resource_id"])
            services.enqueue_discovery(discovery)
    except services.EnqueueUnavailable:
        return error_response("service_unavailable", "Worker queue is unavailable.", status=503)
    return JsonResponse(services.discovery_job_envelope(discovery), status=202)


@router.get("/discoveries/{discovery_id}")
def get_discovery(request, discovery_id: int):
    try:
        discovery = Discovery.objects.get(id=discovery_id)
    except Discovery.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return JsonResponse(services.serialize_discovery(discovery), headers={"Cache-Control": "no-store"})


@router.get("/discoveries/{discovery_id}/endpoints")
def list_discovery_endpoints(
    request,
    discovery_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        discovery = Discovery.objects.get(id=discovery_id)
    except Discovery.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    queryset = discovery.endpoints.order_by("id")
    total = queryset.count()
    items = [services.serialize_endpoint(endpoint) for endpoint in queryset[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/discoveries/{discovery_id}/promote")
def promote_discovery_endpoints(request, discovery_id: int, payload: PromotePayload):
    try:
        discovery = Discovery.objects.get(id=discovery_id)
    except Discovery.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    if discovery.status == "CANCELLED":
        return error_response("conflict", "Cancelled discovery endpoints cannot be promoted.", status=409)

    overrides = payload.target_overrides or {}
    context = {**default_context(), **overrides.get("context", {})}
    promotions = []
    for endpoint in DiscoveredEndpoint.objects.filter(discovery=discovery, id__in=payload.endpoint_ids):
        target, _created = Target.objects.get_or_create(
            host=endpoint.host,
            port=endpoint.port,
            transport=endpoint.transport,
            defaults={
                "protocol_hint": endpoint.suggested_protocol_hint,
                "context": context,
            },
        )
        endpoint.target = target
        endpoint.promoted = True
        endpoint.save(update_fields=["target", "promoted"])
        promotions.append({"endpoint_id": endpoint.id, "target_id": target.id})
    return JsonResponse({"promotions": promotions}, status=201)
