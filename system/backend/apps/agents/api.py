from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from ninja import Query, Router

from apps.agents import services
from apps.agents.models import Agent
from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema


router = Router(tags=["Agents"])


class AgentRegisterPayload(StrictSchema):
    hostname: str
    capabilities: list[str] = []


def _extract_bearer_token(request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.removeprefix("Bearer ").strip()


def _invalid_token():
    return error_response("invalid_token", "Invalid token.", status=401)


@router.get("/agents")
def list_agents(request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    queryset = Agent.objects.all().order_by("hostname")
    total = queryset.count()
    items = [services.serialize_agent(agent) for agent in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/agents/register")
def register_agent(request, payload: AgentRegisterPayload):
    if request.headers.get("X-Bootstrap-Token") != getattr(settings, "AGENT_BOOTSTRAP_TOKEN", "dev-bootstrap-token"):
        return _invalid_token()

    token = services.generate_token()
    now = timezone.now()
    agent, created = Agent.objects.get_or_create(
        hostname=payload.hostname,
        defaults={
            "capabilities": payload.capabilities,
            "agent_token_hash": services.hash_token(token),
            "active": True,
            "last_seen": now,
            "token_rotated_at": now,
        },
    )
    if not created:
        agent.capabilities = payload.capabilities
        agent.agent_token_hash = services.hash_token(token)
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
