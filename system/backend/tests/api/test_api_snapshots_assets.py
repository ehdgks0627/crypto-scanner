import pytest

from tests.api.factories import (
    TARGET_CONTEXT,
    create_asset,
    create_asset_dependency,
    create_risk_score,
    create_snapshot,
    create_target,
)


pytestmark = pytest.mark.django_db


def test_api_snp_001_list_snapshots_returns_latest_first_page(client):
    older = create_snapshot(serial_number="older")
    latest = create_snapshot(serial_number="latest")
    create_asset(snapshot=latest)

    response = client.get("/api/snapshots?limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == latest.id
    assert body["items"][1]["id"] == older.id
    assert {
        "id",
        "scan_job_id",
        "serial_number",
        "asset_count",
        "created_at",
        "summary",
        "validation_errors",
    } <= set(body["items"][0])


def test_api_snp_002_get_snapshot_detail(client):
    snapshot = create_snapshot(serial_number="snap-56")
    create_asset(snapshot=snapshot)

    response = client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == snapshot.id
    assert body["serial_number"] == "snap-56"
    assert body["asset_count"] == 1
    assert {"scan_job_id", "created_at", "summary", "validation_errors"} <= set(body)


def test_api_snp_005_snapshot_scan_job_id_can_be_null_for_imported_snapshots(client):
    snapshot = create_snapshot(serial_number="imported", scan_job=None)

    response = client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 200
    assert response.json()["scan_job_id"] is None


def test_api_snp_003_export_snapshot_returns_cbom_download(client):
    snapshot = create_snapshot(serial_number="snap-56")
    cert = create_asset(snapshot=snapshot, bom_ref="cert:web", name="web certificate", algorithm="RSA-2048", algorithm_family="RSA")
    algorithm = create_asset(snapshot=snapshot, bom_ref="alg:rsa", name="RSA-2048", asset_type="algorithm", algorithm="RSA-2048", algorithm_family="RSA")
    create_risk_score(cert, score=95.0, tier="CRITICAL")
    create_asset_dependency(cert, algorithm, semantic="signature_algorithm")

    response = client.get(f"/api/snapshots/{snapshot.id}/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert f"cbom-{snapshot.id}.json" in response.headers["Content-Disposition"]
    body = response.json()
    assert body["bomFormat"] == "CycloneDX"
    assert body["specVersion"] == "1.6"
    assert body["serialNumber"] == "snap-56"
    assert body["metadata"]["properties"][0] == {"name": "internal:snapshot_id", "value": str(snapshot.id)}
    component = next(item for item in body["components"] if item["bom-ref"] == "cert:web")
    assert component["type"] == "crypto-asset"
    assert component["cryptoProperties"] == {"assetType": "certificate", "algorithm": "RSA-2048", "algorithmFamily": "RSA"}
    assert {"name": "risk.tier", "value": "CRITICAL"} in component["properties"]
    assert body["dependencies"] == [{"ref": "cert:web", "dependsOn": ["alg:rsa"]}]


def test_api_snp_004_diff_snapshots_returns_summary(client):
    snapshot_a = create_snapshot(serial_number="snap-55")
    snapshot_b = create_snapshot(serial_number="snap-56")
    create_asset(snapshot=snapshot_a, bom_ref="cert:unchanged", name="same")
    create_asset(snapshot=snapshot_a, bom_ref="cert:removed", name="old")
    create_asset(snapshot=snapshot_b, bom_ref="cert:unchanged", name="same")
    create_asset(snapshot=snapshot_b, bom_ref="cert:added", name="new")
    create_asset(snapshot=snapshot_b, bom_ref="cert:modified", name="changed")
    create_asset(snapshot=snapshot_a, bom_ref="cert:modified", name="before")
    create_asset(snapshot=snapshot_a, bom_ref="cert:algo", name="same", algorithm="RSA-2048", algorithm_family="RSA")
    create_asset(snapshot=snapshot_b, bom_ref="cert:algo", name="same", algorithm="ML-DSA-65", algorithm_family="ML-DSA")

    response = client.get(f"/api/snapshots/{snapshot_b.id}/diff?other={snapshot_a.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_a"] == snapshot_a.id
    assert body["snapshot_b"] == snapshot_b.id
    assert body["unchanged_count"] == 1
    assert any(item["bom_ref"] == "cert:added" and {"bom_ref", "type", "name"} <= set(item) for item in body["added"])
    assert any(item["bom_ref"] == "cert:removed" and {"bom_ref", "type", "name"} <= set(item) for item in body["removed"])
    modified = next(item for item in body["modified"] if item["bom_ref"] == "cert:modified")
    assert modified["field_changes"]["name"] == ["before", "changed"]
    algorithm_modified = next(item for item in body["modified"] if item["bom_ref"] == "cert:algo")
    assert algorithm_modified["field_changes"]["algorithm"] == ["RSA-2048", "ML-DSA-65"]
    assert algorithm_modified["field_changes"]["algorithm_family"] == ["RSA", "ML-DSA"]


def test_api_ast_001_list_assets_with_filters_and_risk(client):
    snapshot = create_snapshot()
    cert = create_asset(snapshot=snapshot, asset_type="certificate", name="critical cert")
    create_risk_score(cert, score=95.0, tier="CRITICAL")
    low = create_asset(snapshot=snapshot, asset_type="certificate", name="low cert")
    create_risk_score(low, score=20.0, tier="LOW")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/assets?asset_type=certificate&tier=CRITICAL,HIGH&sort=-risk_score"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["asset_type"] == "certificate"
    assert item["risk"]["tier"] == "CRITICAL"
    assert item["snapshot_id"] == snapshot.id
    assert item["bom_ref"] == cert.bom_ref
    assert item["target_label"]
    assert item["summary"]["algorithm"] == cert.algorithm
    assert {"offset", "limit"} <= set(body)


def test_api_ast_001b_list_assets_applies_contract_filters(client):
    snapshot = create_snapshot()
    target = create_target(host="search.testbed.local")
    match = create_asset(snapshot=snapshot, target=target, asset_class="crypto", asset_type="certificate", name="Searchable Cert", bom_ref="asset:match")
    miss = create_asset(snapshot=snapshot, asset_class="crypto", asset_type="key", name="Other Key", bom_ref="asset:miss", algorithm_family="ML-DSA")
    create_risk_score(match, score=88.0, tier="HIGH")
    create_risk_score(miss, score=20.0, tier="LOW")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/assets"
        f"?asset_class=crypto&asset_type=certificate&target_id={target.id}"
        "&min_score=80&max_score=90&tier=HIGH&q=searchable&quantum_vulnerable=true"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == match.id


def test_api_ast_002_get_asset_detail_with_context_sources(client):
    from apps.assets.models import AssetContextOverride

    target = create_target(context={**TARGET_CONTEXT, "criticality": "medium"})
    old_snapshot = create_snapshot(serial_number="old-risk")
    old_asset = create_asset(snapshot=old_snapshot, target=target, bom_ref="asset:history")
    create_risk_score(old_asset, score=72.0, tier="HIGH")
    asset = create_asset(target=target, bom_ref="asset:history")
    create_risk_score(asset, score=91.0, tier="CRITICAL", factors={"A": 0.9, "D": 0.8, "E": 0.7, "L": 0.6, "C": 0.5})
    AssetContextOverride.objects.create(asset=asset, sensitivity="critical", criticality=None)

    response = client.get(f"/api/assets/{asset.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_context"]["sensitivity"] == "critical"
    assert body["effective_context"]["criticality"] == "medium"
    assert body["context_override"]["criticality"] is None
    assert body["context_sources"]["sensitivity"] == "asset_override"
    assert body["context_sources"]["criticality"] == "target"
    assert body["snapshot_id"] == asset.snapshot_id
    assert body["bom_ref"] == asset.bom_ref
    assert body["target"]["port"] == target.port
    assert body["crypto_properties"]["algorithm"] == asset.algorithm
    assert body["properties"]["bom_ref"] == asset.bom_ref
    assert body["risk"]["score"] == 91
    assert body["risk"]["factor_a"] == 0.9
    assert body["dependencies"] == {"dependsOn": [], "dependedBy": []}
    assert [item["snapshot_id"] for item in body["history"]] == [old_snapshot.id, asset.snapshot_id]


def test_api_ast_002b_asset_dependencies_are_cbom_component_edges(client):
    snapshot = create_snapshot()
    certificate = create_asset(snapshot=snapshot, bom_ref="cert:web", name="web certificate")
    key = create_asset(snapshot=snapshot, bom_ref="key:web", name="web public key", asset_type="key")
    create_asset_dependency(certificate, key, semantic="embeds_key")

    certificate_response = client.get(f"/api/assets/{certificate.id}")
    key_response = client.get(f"/api/assets/{key.id}")

    assert certificate_response.status_code == 200
    assert key_response.status_code == 200
    assert certificate_response.json()["dependencies"] == {
        "dependsOn": [{"id": key.id, "bom_ref": "key:web", "name": "web public key", "semantic": "embeds_key"}],
        "dependedBy": [],
    }
    assert key_response.json()["dependencies"] == {
        "dependsOn": [],
        "dependedBy": [{"id": certificate.id, "bom_ref": "cert:web", "name": "web certificate", "semantic": "embeds_key"}],
    }


def test_api_ast_003_context_patch_distinguishes_omit_and_null(client):
    from apps.assets.models import AssetContextOverride

    target = create_target(
        context={
            **TARGET_CONTEXT,
            "sensitivity": "high",
            "criticality": "medium",
            "lifespan_years": 5,
        }
    )
    asset = create_asset(target=target)
    AssetContextOverride.objects.create(
        asset=asset,
        sensitivity="critical",
        criticality="high",
        lifespan_years=10,
    )

    response = client.patch(
        f"/api/assets/{asset.id}/context",
        data={"criticality": "critical", "lifespan_years": None},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["context_override"]["sensitivity"] == "critical"
    assert body["context_override"]["criticality"] == "critical"
    assert body["context_override"]["lifespan_years"] is None
    assert body["effective_context"]["lifespan_years"] == 5
    assert body["context_sources"]["lifespan_years"] == "target"
    assert body["asset_id"] == asset.id
    assert body["applied_overrides"] == {"criticality": "critical", "lifespan_years": None}
    assert body["recompute_job_id"] is not None


def test_api_ast_003b_context_patch_rejects_invalid_context_values(client):
    asset = create_asset()

    response = client.patch(
        f"/api/assets/{asset.id}/context",
        data={"sensitivity": "extreme", "lifespan_years": -1},
        content_type="application/json",
    )

    assert response.status_code == 422


def test_api_ast_004_context_patch_enqueue_failure_rolls_back(client, monkeypatch):
    from apps.assets import services
    from apps.assets.models import AssetContextOverride
    from apps.jobs.models import AsyncJob

    asset = create_asset()
    AssetContextOverride.objects.create(asset=asset, sensitivity="high")

    def fail_enqueue(async_job):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_asset_recompute", fail_enqueue)

    response = client.patch(
        f"/api/assets/{asset.id}/context",
        data={"sensitivity": "critical"},
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    override = AssetContextOverride.objects.get(asset=asset)
    assert override.sensitivity == "high"
    assert AsyncJob.objects.count() == 0


def test_api_ast_005_qualitative_request_updates_existing_record(client):
    from apps.assets.models import QualitativeAssessment

    asset = create_asset()
    assessment = QualitativeAssessment.objects.create(
        asset=asset,
        provider="stub",
        summary="old summary",
        threat_scenarios=[],
        migration_recommendation="old",
        confidence=0.2,
    )

    response = client.post(f"/api/assets/{asset.id}/qualitative")

    assert response.status_code == 200
    body = response.json()
    assert {
        "provider",
        "prompt_version",
        "summary",
        "threat_scenarios",
        "migration_recommendation",
        "dhs_criteria",
        "confidence",
        "generated_at",
    } <= set(body)
    assert QualitativeAssessment.objects.count() == 1
    assessment.refresh_from_db()
    assert assessment.summary == body["summary"]
    assert assessment.prompt_version == body["prompt_version"]
    assert assessment.prompt_payload["asset"]["id"] == asset.id


def test_api_ast_006_qualitative_request_uses_asset_context_and_risk(client):
    target_a = create_target(
        host="api.testbed.local",
        context={
            "sensitivity": "critical",
            "lifespan_years": 12,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "customer-api",
        },
    )
    target_b = create_target(
        host="archive.testbed.local",
        port=8443,
        context={
            "sensitivity": "low",
            "lifespan_years": 1,
            "criticality": "low",
            "exposure": "air_gapped",
            "service_role": "archive",
        },
    )
    rsa_asset = create_asset(
        target=target_a,
        name="customer API certificate",
        bom_ref="qualitative:rsa",
        algorithm="RSA-2048",
        algorithm_family="RSA",
    )
    pqc_asset = create_asset(
        target=target_b,
        name="archive signing key",
        bom_ref="qualitative:pqc",
        algorithm="ML-DSA-65",
        algorithm_family="ML-DSA",
    )
    create_risk_score(rsa_asset, score=95.0, tier="CRITICAL")
    create_risk_score(pqc_asset, score=25.0, tier="LOW")

    rsa_response = client.post(f"/api/assets/{rsa_asset.id}/qualitative")
    pqc_response = client.post(f"/api/assets/{pqc_asset.id}/qualitative")

    assert rsa_response.status_code == 200
    assert pqc_response.status_code == 200
    rsa_body = rsa_response.json()
    pqc_body = pqc_response.json()
    assert rsa_body["summary"] != pqc_body["summary"]
    assert rsa_body["confidence"] != pqc_body["confidence"]
    assert "ssh.testbed.local" not in rsa_body["summary"]
    assert "ssh.testbed.local" not in pqc_body["summary"]
    assert rsa_body["migration_recommendation"] != "Plan migration to a PQC or hybrid alternative."
    assert "harvest_now_decrypt_later" in rsa_body["threat_scenarios"]
    assert 0 <= rsa_body["confidence"] <= 1
    assert 0 <= pqc_body["confidence"] <= 1
    assert rsa_body["prompt_version"] == "qualitative-risk-v2"
    assert pqc_body["prompt_version"] == "qualitative-risk-v2"
    assert rsa_body["dhs_criteria"]["asset_value"]["rating"] in {"high", "critical"}
    assert "public_internet" in rsa_body["dhs_criteria"]["asset_value"]["signals"][0]
    assert 0 <= rsa_body["dhs_criteria"]["asset_value"]["score"] <= 1


def test_api_ast_007_qualitative_worker_processes_asset_task():
    from apps.assets import services
    from apps.assets.models import QualitativeAssessment
    from apps.jobs.models import QueuedTask

    target = create_target(
        host="worker-api.testbed.local",
        context={
            "sensitivity": "critical",
            "lifespan_years": 15,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "customer-api",
        },
    )
    asset = create_asset(
        target=target,
        name="worker API certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        bom_ref="qualitative:worker:rsa",
        metadata={
            "scanner": "agent.app_config",
            "path": "/etc/nginx/nginx.conf",
            "certificate_paths": ["/etc/nginx/ssl/server.crt"],
            "private_key_paths": ["/etc/nginx/ssl/server.key"],
        },
    )
    task = services.enqueue_qualitative_assessment(asset.id)

    result = services.process_next_qualitative_assessment_task()

    task.refresh_from_db()
    assessment = QualitativeAssessment.objects.get(asset=asset)
    assert task.status == QueuedTask.COMPLETED
    assert task.task_name == "qualitative_assessment"
    assert result == {
        "asset_id": asset.id,
        "assessment_id": assessment.id,
        "provider": "mock-rulebook",
    }
    assert "worker API certificate" in assessment.summary
    assert "harvest_now_decrypt_later" in assessment.threat_scenarios
    assert assessment.prompt_version == "qualitative-risk-v2"
    assert assessment.prompt_payload["asset"]["name"] == "worker API certificate"
    assert assessment.prompt_payload["context"]["exposure"] == "public_internet"
    assert assessment.prompt_payload["operational_context"]["connected_service"]["label"] == "worker-api.testbed.local:443"
    assert assessment.prompt_payload["operational_context"]["data_classification"] == {"level": "critical", "source": "target"}
    assert assessment.prompt_payload["operational_context"]["file_paths"] == [
        "/etc/nginx/nginx.conf",
        "/etc/nginx/ssl/server.crt",
        "/etc/nginx/ssl/server.key",
    ]
    assert isinstance(assessment.threat_scenarios, list)
    assert assessment.dhs_criteria["asset_value"]["rating"] == "critical"
    assert "service_role:customer-api" in assessment.dhs_criteria["asset_value"]["signals"]
    assert isinstance(assessment.confidence, float)


def test_api_ast_008_qualitative_worker_falls_back_when_llm_response_is_invalid(monkeypatch):
    from apps.assets import services
    from apps.assets.models import QualitativeAssessment

    target = create_target(
        host="fallback-api.testbed.local",
        context={
            "sensitivity": "critical",
            "lifespan_years": 10,
            "criticality": "high",
            "exposure": "public_internet",
            "service_role": "fallback-api",
        },
    )
    asset = create_asset(
        target=target,
        name="fallback API certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        bom_ref="qualitative:fallback:rsa",
    )

    monkeypatch.setattr(services, "_mock_qualitative_llm_response", lambda _payload: "invalid response without JSON")

    task = services.enqueue_qualitative_assessment(asset.id)
    result = services.process_next_qualitative_assessment_task()

    task.refresh_from_db()
    assessment = QualitativeAssessment.objects.get(asset=asset)
    assert result["provider"] == "mock-rulebook-fallback"
    assert task.status == "COMPLETED"
    assert assessment.provider == "mock-rulebook-fallback"
    assert assessment.prompt_payload["llm_fallback"] == {
        "used": True,
        "reason": "QualitativeRiskResponseParseError",
    }
    assert "fallback API certificate" in assessment.summary
    assert "harvest_now_decrypt_later" in assessment.threat_scenarios
    assert assessment.migration_recommendation
    assert assessment.dhs_criteria["asset_value"]["question"].startswith("Q1:")
    assert assessment.dhs_criteria["asset_value"]["rating"] in {"high", "critical"}
    assert 0 <= assessment.confidence <= 1


def test_api_ast_009_qualitative_request_reuses_cache_until_prompt_changes(monkeypatch):
    from apps.assets import services
    from apps.assets.models import AssetContextOverride

    target = create_target(
        host="cache-api.testbed.local",
        context={
            "sensitivity": "low",
            "lifespan_years": 2,
            "criticality": "medium",
            "exposure": "internal_network",
            "service_role": "cache-api",
        },
    )
    asset = create_asset(
        target=target,
        name="cache API certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        bom_ref="qualitative:cache:rsa",
    )
    original_provider = services._mock_qualitative_llm_response
    calls = {"count": 0}

    def tracked_provider(payload):
        calls["count"] += 1
        return original_provider(payload)

    monkeypatch.setattr(services, "_mock_qualitative_llm_response", tracked_provider)

    first = services.refresh_qualitative_assessment(asset.id)
    second = services.refresh_qualitative_assessment(asset.id)

    assert first.id == second.id
    assert calls["count"] == 1
    assert second.prompt_payload["llm_cache"]["key"]
    assert second.prompt_payload["llm_fallback"] == {"used": False, "reason": None}

    AssetContextOverride.objects.create(asset=asset, sensitivity="critical")
    third = services.refresh_qualitative_assessment(asset.id)

    assert third.id == first.id
    assert calls["count"] == 2
    assert third.prompt_payload["context"]["sensitivity"] == "critical"
