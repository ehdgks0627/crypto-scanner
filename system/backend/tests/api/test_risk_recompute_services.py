import pytest

from tests.api.factories import create_asset, create_snapshot, create_target


pytestmark = pytest.mark.django_db


def test_recompute_snapshot_upserts_risk_scores_with_factor_metadata():
    from apps.risk import services
    from apps.risk.models import RiskScore

    target = create_target(
        ip="8.8.8.8",
        context={
            "sensitivity": "critical",
            "lifespan_years": 25,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "pki",
        },
    )
    snapshot = create_snapshot()
    rsa_asset = create_asset(
        snapshot=snapshot,
        target=target,
        bom_ref="cert:rsa",
        algorithm="RSA-2048",
        algorithm_family="RSA",
    )
    pqc_asset = create_asset(
        snapshot=snapshot,
        target=target,
        bom_ref="cert:pqc",
        algorithm="ML-DSA-65",
        algorithm_family="ML-DSA",
    )

    result = services.recompute_snapshot_risks(
        snapshot.id,
        {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0},
    )

    assert result == {"snapshot_id": snapshot.id, "updated_scores_count": 2}
    rsa_score = RiskScore.objects.get(asset=rsa_asset)
    pqc_score = RiskScore.objects.get(asset=pqc_asset)
    assert rsa_score.score == 95
    assert rsa_score.tier == "CRITICAL"
    assert rsa_score.factors["a"] == 0.95
    assert rsa_score.factors["sources"]["a"] == "algorithm_table"
    assert rsa_score.factors["sources"]["d"] == "target"
    assert pqc_score.score == 0
    assert pqc_score.tier == "LOW"


def test_recompute_asset_uses_asset_override_before_target_context():
    from apps.assets.models import AssetContextOverride
    from apps.risk import services
    from apps.risk.models import RiskScore

    target = create_target(
        context={
            "sensitivity": "low",
            "lifespan_years": 1,
            "criticality": "low",
            "exposure": "air_gapped",
            "service_role": "web-frontend",
        },
    )
    asset = create_asset(target=target, algorithm="RSA-2048", algorithm_family="RSA")
    AssetContextOverride.objects.create(
        asset=asset,
        sensitivity="critical",
        lifespan_years=25,
        criticality="critical",
        exposure="public_internet",
    )

    result = services.recompute_asset_risk(asset.id)

    score = RiskScore.objects.get(asset=asset)
    assert result == {"asset_id": asset.id, "snapshot_id": asset.snapshot_id, "updated_scores_count": 1}
    assert score.score == 95
    assert score.factors["sources"]["d"] == "asset_override"
    assert score.factors["sources"]["e"] == "asset_override"


def test_recompute_task_processes_queued_job_and_persists_weights():
    from apps.jobs.models import AsyncJob, QueuedTask
    from apps.risk import services
    from apps.risk.models import RiskScore, RiskWeights

    snapshot = create_snapshot()
    create_asset(snapshot=snapshot, algorithm="RSA-2048", algorithm_family="RSA")
    async_job = services.create_recompute_job(
        snapshot.id,
        {
            "weights": {"wA": 0.5, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0},
            "persist_weights_as_default": True,
        },
    )
    task = QueuedTask.objects.get(async_job=async_job)

    processed = services.process_recompute_task(task.id)

    async_job.refresh_from_db()
    task.refresh_from_db()
    assert processed["updated_scores_count"] == 1
    assert async_job.status == AsyncJob.COMPLETED
    assert async_job.result == {"snapshot_id": snapshot.id, "updated_scores_count": 1}
    assert task.status == QueuedTask.COMPLETED
    assert RiskScore.objects.filter(snapshot=snapshot).count() == 1
    assert RiskWeights.objects.get().wA == 0.5
