from secrets import compare_digest
from typing import Literal

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from ninja import Query, Router
from pydantic import AnyUrl

from apps.agents import services
from apps.agents.models import Agent
from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema


router = Router(tags=["Agents"])
AgentRole = Literal["host", "discovery"]


class AgentRegisterPayload(StrictSchema):
    hostname: str
    agent_role: AgentRole = "host"
    agent_url: AnyUrl | None = None
    capabilities: list[str] = []
    os_distribution: str | None = None


def _extract_bearer_token(request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.removeprefix("Bearer ").strip()


def _invalid_token():
    return error_response("invalid_token", "Invalid token.", status=401)


@router.get("/agents")
def list_agents(
    request,
    active: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    agent_role: AgentRole | None = None,
):
    queryset = Agent.objects.all().order_by("hostname")
    if active is not None:
        queryset = queryset.filter(active=active)
    if agent_role is not None:
        queryset = queryset.filter(agent_role=agent_role)
    total = queryset.count()
    items = [services.serialize_agent(agent) for agent in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/agents/register")
def register_agent(request, payload: AgentRegisterPayload):
    provided_token = request.headers.get("X-Bootstrap-Token", "")
    expected_token = getattr(settings, "AGENT_BOOTSTRAP_TOKEN", "dev-bootstrap-token")
    if not provided_token or not compare_digest(provided_token, expected_token):
        return _invalid_token()

    token = services.generate_token()
    now = timezone.now()
    agent, created = Agent.objects.get_or_create(
        hostname=payload.hostname,
        agent_role=payload.agent_role,
        defaults={
            "agent_url": str(payload.agent_url) if payload.agent_url else None,
            "capabilities": payload.capabilities,
            "os_distribution": payload.os_distribution,
            "agent_token_hash": services.hash_token(token),
            "agent_runtime_token": token,
            "active": True,
            "last_seen": now,
            "token_rotated_at": now,
        },
    )
    if not created:
        agent.agent_role = payload.agent_role
        agent.agent_url = str(payload.agent_url) if payload.agent_url else None
        agent.capabilities = payload.capabilities
        agent.os_distribution = payload.os_distribution
        agent.agent_token_hash = services.hash_token(token)
        agent.agent_runtime_token = token
        agent.active = True
        agent.last_seen = now
        agent.token_rotated_at = now
        agent.save()

    status = 201 if created else 200
    return JsonResponse(
        {
            "id": str(agent.id),
            "agent_token": token,
            "registration_action": "created" if created else "token_rotated",
            "token_rotated_at": services.serialize_agent(agent)["token_rotated_at"],
        },
        status=status,
    )


@router.get("/agents/{agent_id}")
def get_agent(request, agent_id: str):
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return services.serialize_agent(agent)


@router.post("/agents/{agent_id}/heartbeat")
def heartbeat_agent(request, agent_id: str):
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return _invalid_token()
    if not services.validate_agent_token(agent, _extract_bearer_token(request)):
        return _invalid_token()
    agent.last_seen = timezone.now()
    agent.save(update_fields=["last_seen"])
    return {"received_at": services.serialize_agent(agent)["last_seen"]}


@router.delete("/agents/{agent_id}")
def delete_agent(request, agent_id: str):
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    agent.active = False
    agent.save(update_fields=["active"])
    return HttpResponse(status=204)
