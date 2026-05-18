import re
from ipaddress import ip_address, ip_network
from typing import Annotated, Literal
from uuid import UUID

from django.db import transaction
from django.http import JsonResponse
from ninja import Query, Router
from pydantic import Field, model_validator

from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema
from apps.agents import services as agent_services
from apps.agents.models import Agent
from apps.discoveries import services
from apps.discoveries.models import DiscoveredEndpoint, Discovery
from apps.jobs.models import AsyncJob
from apps.targets.models import Target, default_context


router = Router(tags=["Discoveries"])


JobStatusParam = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
PortNumber = Annotated[int, Field(ge=1, le=65535)]
DiscoveryScopeType = Literal["cidr", "ip", "domain"]
DiscoveryExecutorType = Literal["central", "agent"]


DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class DiscoveryCreate(StrictSchema):
    scope_type: DiscoveryScopeType | None = None
    scope_value: str | None = Field(default=None, max_length=253)
    cidr: str | None = None
    executor_type: DiscoveryExecutorType = "central"
    agent_id: UUID | None = None
    ports: list[PortNumber] | None = None
    include_default_ports: bool = True
    auto_scan: bool = True
    auto_availability_check: bool = True

    @model_validator(mode="after")
    def normalize_scope(self):
        scope_type = self.scope_type or "cidr"
        scope_value = self.scope_value if self.scope_value is not None else self.cidr
        if scope_value is None:
            raise ValueError("scope_value is required.")

        normalized_value = validate_scope(scope_type, scope_value)
        self.scope_type = scope_type
        self.scope_value = normalized_value
        self.cidr = normalized_value
        if self.executor_type == "central" and self.agent_id is not None:
            raise ValueError("agent_id is only valid when executor_type is agent.")
        if self.executor_type == "agent" and self.agent_id is None:
            raise ValueError("agent_id is required when executor_type is agent.")
        return self


class PromotionContextPayload(StrictSchema):
    sensitivity: Literal["low", "medium", "high", "critical"] | None = None
    lifespan_years: int | None = Field(default=None, ge=0)
    criticality: Literal["low", "medium", "high", "critical"] | None = None
    exposure: Literal["public_internet", "dmz", "internal_network", "air_gapped"] | None = None
    service_role: str | None = None


class DiscoveryPromotionPayload(StrictSchema):
    endpoint_id: int
    host: str
    protocol_hint: Literal["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]
    context: PromotionContextPayload | None = None
    agent_enabled: bool = False


class PromotePayload(StrictSchema):
    promotions: list[DiscoveryPromotionPayload] = Field(min_length=1)


def validate_scope(scope_type: DiscoveryScopeType, scope_value: str) -> str:
    value = scope_value.strip()
    if not value:
        raise ValueError("scope_value is required.")
    if scope_type == "cidr":
        if "/" not in value:
            raise ValueError("CIDR scope must use CIDR notation.")
        try:
            ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("scope_value must be a valid CIDR.") from exc
        return value
    if scope_type == "ip":
        try:
            ip_address(value)
        except ValueError as exc:
            raise ValueError("scope_value must be a valid IP address.") from exc
        return value
    if not is_valid_domain(value):
        raise ValueError("scope_value must be a valid domain name.")
    return value.lower()


def is_valid_domain(value: str) -> bool:
    domain = value.rstrip(".")
    if not domain or len(domain) > 253 or "/" in domain or ":" in domain:
        return False
    return all(DOMAIN_LABEL_RE.match(label) for label in domain.split("."))


def get_usable_discovery_agent(agent_id: UUID):
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return None, error_response("agent_unavailable", "Discovery agent not found.", status=422)
    if agent.agent_role != Agent.ROLE_DISCOVERY:
        return None, error_response("agent_unavailable", "Selected agent is not a Discovery Agent.", status=422)
    if not agent.active:
        return None, error_response("agent_unavailable", "Discovery agent is inactive.", status=409)
    if agent_services.is_stale(agent):
        return None, error_response("agent_unavailable", "Discovery agent heartbeat is stale.", status=409)
    if "agent.discovery" not in agent.capabilities:
        return None, error_response("agent_unavailable", "Selected agent does not support discovery.", status=422)
    if not agent.agent_url or not agent.agent_runtime_token:
        return None, error_response("agent_unavailable", "Discovery agent is missing connection credentials.", status=409)
    return agent, None


@router.get("/discoveries")
def list_discoveries(
    request,
    status: JobStatusParam | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    queryset = Discovery.objects.select_related("async_job", "discovery_agent").order_by("-updated_at", "-id")
    if status:
        queryset = queryset.filter(status=status)
    total = queryset.count()
    items = [services.serialize_discovery(discovery) for discovery in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/discoveries")
def create_discovery(request, payload: DiscoveryCreate):
    discovery_agent = None
    if payload.executor_type == "agent":
        discovery_agent, agent_error = get_usable_discovery_agent(payload.agent_id)
        if agent_error:
            return agent_error

    try:
        with transaction.atomic():
            discovery = (
                Discovery.objects.select_for_update()
                .filter(
                    scope_type=payload.scope_type,
                    scope_value=payload.scope_value,
                    executor_type=payload.executor_type,
                    discovery_agent=discovery_agent,
                )
                .order_by("-id")
                .first()
            )
            if discovery and discovery.status in {AsyncJob.PENDING, AsyncJob.RUNNING}:
                return JsonResponse(services.discovery_job_envelope(discovery), status=202)

            async_job = AsyncJob.objects.create(
                kind="discovery",
                status=AsyncJob.PENDING,
                request_payload=payload.model_dump(exclude_none=True, mode="json"),
            )
            if discovery:
                discovery.async_job = async_job
                discovery.cidr = payload.cidr
                discovery.ports = payload.ports or []
                discovery.include_default_ports = payload.include_default_ports
                discovery.status = async_job.status
                discovery.started_at = None
                discovery.finished_at = None
                discovery.error = None
                discovery.save(
                    update_fields=[
                        "async_job",
                        "cidr",
                        "ports",
                        "include_default_ports",
                        "status",
                        "started_at",
                        "finished_at",
                        "error",
                        "updated_at",
                    ]
                )
            else:
                discovery = Discovery.objects.create(
                    async_job=async_job,
                    scope_type=payload.scope_type,
                    scope_value=payload.scope_value,
                    cidr=payload.cidr,
                    executor_type=payload.executor_type,
                    discovery_agent=discovery_agent,
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
        discovery = Discovery.objects.select_related("async_job", "discovery_agent").get(id=discovery_id)
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

    promoted = []
    skipped = []
    endpoints = {
        endpoint.id: endpoint
        for endpoint in DiscoveredEndpoint.objects.filter(
            discovery=discovery,
            id__in=[promotion.endpoint_id for promotion in payload.promotions],
        )
    }

    for promotion in payload.promotions:
        endpoint = endpoints.get(promotion.endpoint_id)
        if endpoint is None:
            skipped.append({"endpoint_id": promotion.endpoint_id, "reason": "endpoint_not_found"})
            continue
        if endpoint.promoted:
            skipped.append({"endpoint_id": promotion.endpoint_id, "reason": "already_promoted"})
            continue

        context = {**default_context(), **((promotion.context.model_dump() if promotion.context else {}) or {})}
        target, _created = Target.objects.get_or_create(
            host=promotion.host,
            port=endpoint.port,
            transport=endpoint.transport,
            defaults={
                "protocol_hint": promotion.protocol_hint,
                "context": context,
                "agent_enabled": promotion.agent_enabled,
            },
        )
        endpoint.target = target
        endpoint.promoted = True
        endpoint.save(update_fields=["target", "promoted"])
        promoted.append({"endpoint_id": endpoint.id, "target_id": target.id})
    return JsonResponse({"promoted": promoted, "skipped": skipped}, status=201)
