from ninja import Router

from apps.agents.models import Agent
from apps.agents.services import is_stale
from apps.jobs.models import AsyncJob
from apps.jobs.services import serialize_job
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot


router = Router(tags=["Dashboard"])


@router.get("/dashboard/summary")
def get_dashboard_summary(request):
    latest = CbomSnapshot.objects.order_by("-id").first()
    agents = list(Agent.objects.all())
    agent_status = {
        "total": len(agents),
        "active": len([agent for agent in agents if agent.active]),
        "stale": len([agent for agent in agents if agent.active and is_stale(agent)]),
    }
    recent_jobs = [serialize_job(job) for job in AsyncJob.objects.order_by("-id")[:5]]

    if latest is None:
        return {
            "snapshot": None,
            "by_tier": {},
            "by_asset_type": {},
            "by_algorithm_family": {},
            "quantum_vulnerable_ratio": 0,
            "recent_jobs": recent_jobs,
            "agents_status": agent_status,
            "trend": [],
        }

    risk_scores = list(RiskScore.objects.filter(snapshot=latest).select_related("asset"))
    by_tier = {}
    by_asset_type = {}
    by_algorithm_family = {}
    vulnerable_count = 0
    for risk_score in risk_scores:
        by_tier[risk_score.tier] = by_tier.get(risk_score.tier, 0) + 1
        asset = risk_score.asset
        by_asset_type[asset.asset_type] = by_asset_type.get(asset.asset_type, 0) + 1
        by_algorithm_family[asset.algorithm_family] = by_algorithm_family.get(asset.algorithm_family, 0) + 1
        if asset.algorithm_family in {"RSA", "ECDSA", "ECDH", "DH"}:
            vulnerable_count += 1
    ratio = vulnerable_count / len(risk_scores) if risk_scores else 0
    return {
        "snapshot": {"id": latest.id, "serial_number": latest.serial_number},
        "by_tier": by_tier,
        "by_asset_type": by_asset_type,
        "by_algorithm_family": by_algorithm_family,
        "quantum_vulnerable_ratio": ratio,
        "recent_jobs": recent_jobs,
        "agents_status": agent_status,
        "trend": [],
    }
