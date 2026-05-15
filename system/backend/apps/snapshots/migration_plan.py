from apps.risk.models import RiskScore
from migration_engine import recommend_migration


def snapshot_migration_plan_items(snapshot):
    queryset = (
        RiskScore.objects.filter(snapshot=snapshot)
        .select_related("asset", "asset__target")
        .order_by("-score", "asset_id")
    )
    return [recommend_for_risk_score(risk_score) for risk_score in queryset]


def recommend_for_risk_score(risk_score):
    asset = risk_score.asset
    context = risk_score.factors.get("context", {}) if isinstance(risk_score.factors, dict) else {}
    return recommend_migration(
        asset_id=risk_score.asset_id,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        algorithm=asset.algorithm,
        algorithm_family=asset.algorithm_family,
        risk_score=round(risk_score.score),
        tier=risk_score.tier,
        context=context,
        capabilities=migration_capabilities(asset),
    )


def migration_capabilities(asset):
    capabilities = {"inventory_fresh"}
    if asset.target:
        capabilities.add("owner_known")
        if asset.target.agent_enabled:
            capabilities.update({"config_policy", "rescan_validation"})
        if asset.target.context and asset.target.context.get("service_role"):
            capabilities.add("canary_supported")
    if asset.asset_type in {"certificate", "key"}:
        capabilities.add("rollback_supported")
    return sorted(capabilities)
