import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.jobs.models import ScanRunLog


STALE_AFTER = timezone.timedelta(minutes=5)


def hash_token(token: str) -> str:
    return make_password(token)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def is_stale(agent) -> bool:
    if not agent.last_seen:
        return True
    return agent.last_seen < timezone.now() - STALE_AFTER


def serialize_agent(agent):
    return {
        "id": str(agent.id),
        "hostname": agent.hostname,
        "capabilities": agent.capabilities,
        "active": agent.active,
        "last_seen": agent.last_seen.isoformat().replace("+00:00", "Z") if agent.last_seen else None,
        "token_rotated_at": agent.token_rotated_at.isoformat().replace("+00:00", "Z")
        if agent.token_rotated_at
        else None,
        "is_stale": is_stale(agent),
    }


def validate_agent_token(agent, token: str | None) -> bool:
    if not token or not agent.active:
        return False
    return check_password(token, agent.agent_token_hash)


def record_agent_scanner_skip_if_needed(async_job, target, scanner_kind: str):
    from apps.agents.models import Agent

    if not target.agent_enabled:
        return False
    agent = Agent.objects.filter(hostname=target.host, active=True).first()
    error = None
    if not agent:
        error = "agent_unavailable"
    elif is_stale(agent):
        error = "agent_stale"
    elif scanner_kind not in agent.capabilities:
        error = "capability_unsupported"

    if not error:
        return False
    ScanRunLog.objects.create(
        async_job=async_job,
        target=target,
        scanner_kind=scanner_kind,
        status="SKIPPED",
        findings_count=0,
        error=error,
    )
    return True
