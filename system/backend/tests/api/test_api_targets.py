import pytest


pytestmark = pytest.mark.django_db


TARGET_CONTEXT = {
    "sensitivity": "high",
    "lifespan_years": 10,
    "criticality": "high",
    "exposure": "internal_network",
    "service_role": "web-frontend",
}


def create_target(**overrides):
    from apps.targets.models import Target

    values = {
        "host": "web.testbed.local",
        "display_name": None,
        "ip": None,
        "port": 443,
        "protocol_hint": "TLS",
        "sni": None,
        "transport": "TCP",
        "agent_enabled": True,
        "agent_url": None,
        "context": TARGET_CONTEXT,
    }
    values.update(overrides)
    return Target.objects.create(**values)


def assert_target_shape(target):
    assert {
        "id",
        "host",
        "display_name",
        "ip",
        "port",
        "protocol_hint",
        "sni",
        "transport",
        "agent_enabled",
        "agent_url",
        "context",
        "created_at",
        "updated_at",
    } <= set(target)
    assert {
        "sensitivity",
        "lifespan_years",
        "criticality",
        "exposure",
        "service_role",
    } == set(target["context"])


def test_api_tgt_001_list_targets_filters_by_host(client):
    create_target(host="web.testbed.local")
    create_target(host="db.testbed.local", port=5432, protocol_hint="UNKNOWN")

    response = client.get("/api/targets?host=web&limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 0
    assert body["limit"] == 20
    assert len(body["items"]) == 1
    assert "web" in body["items"][0]["host"]
    assert_target_shape(body["items"][0])


def test_api_tgt_002_create_target_returns_schema_with_default_context(client):
    response = client.post(
        "/api/targets",
        data={
            "host": "api.testbed.local",
            "display_name": "API Gateway",
            "port": 8443,
            "protocol_hint": "TLS",
            "transport": "TCP",
            "context": {"criticality": "critical"},
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["host"] == "api.testbed.local"
    assert body["display_name"] == "API Gateway"
    assert body["port"] == 8443
    assert body["transport"] == "TCP"
    assert body["context"] == {
        "sensitivity": None,
        "lifespan_years": None,
        "criticality": "critical",
        "exposure": None,
        "service_role": None,
    }
    assert_target_shape(body)


def test_api_tgt_003_get_target_detail(client):
    target = create_target()

    response = client.get(f"/api/targets/{target.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == target.id
    assert body["host"] == "web.testbed.local"
    assert body["display_name"] is None
    assert body["port"] == 443
    assert body["protocol_hint"] == "TLS"
    assert body["transport"] == "TCP"
    assert body["context"] == TARGET_CONTEXT
    assert_target_shape(body)


def test_api_tgt_004_duplicate_target_returns_conflict(client):
    create_target(host="dup.testbed.local", port=443, transport="TCP")

    response = client.post(
        "/api/targets",
        data={
            "host": "dup.testbed.local",
            "port": 443,
            "protocol_hint": "TLS",
            "transport": "TCP",
        },
        content_type="application/json",
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "conflict"
    assert body["message"]
    assert isinstance(body["details"], dict)
    assert "detail" not in body


def test_api_tgt_005_context_patch_returns_recompute_job_id(client):
    from apps.jobs.models import AsyncJob

    target = create_target(context={**TARGET_CONTEXT, "criticality": "high"})

    response = client.patch(
        f"/api/targets/{target.id}",
        data={"context": {"criticality": "critical"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target"]["id"] == target.id
    assert body["target"]["context"]["criticality"] == "critical"
    assert body["recompute_job_id"] is not None
    job = AsyncJob.objects.get(id=body["recompute_job_id"])
    assert job.kind == "recompute"
    assert job.resource_id == job.id


def test_api_tgt_006_context_patch_enqueue_failure_rolls_back(client, monkeypatch):
    from apps.jobs.models import AsyncJob
    from apps.targets import services
    from apps.targets.models import Target

    target = create_target(context={**TARGET_CONTEXT, "criticality": "high"})

    def fail_enqueue(async_job):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_target_recompute", fail_enqueue)

    response = client.patch(
        f"/api/targets/{target.id}",
        data={"context": {"criticality": "critical"}},
        content_type="application/json",
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "service_unavailable"
    target.refresh_from_db()
    assert target.context["criticality"] == "high"
    assert Target.objects.count() == 1
    assert AsyncJob.objects.count() == 0


def test_api_tgt_007_noop_patch_does_not_create_recompute_job(client):
    from apps.jobs.models import AsyncJob

    target = create_target(context={**TARGET_CONTEXT, "criticality": "high"})

    response = client.patch(
        f"/api/targets/{target.id}",
        data={"context": {"criticality": "high"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target"]["context"]["criticality"] == "high"
    assert body["recompute_job_id"] is None
    assert AsyncJob.objects.count() == 0


def test_api_tgt_007b_display_name_patch_does_not_create_recompute_job(client):
    from apps.jobs.models import AsyncJob

    target = create_target(display_name=None)

    response = client.patch(
        f"/api/targets/{target.id}",
        data={"display_name": "Web Server #2"},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target"]["display_name"] == "Web Server #2"
    assert body["recompute_job_id"] is None
    assert AsyncJob.objects.count() == 0


def test_api_tgt_007c_display_name_is_trimmed_and_blank_becomes_null(client):
    created = client.post(
        "/api/targets",
        data={"host": "name.testbed.local", "display_name": "  Named Target  ", "port": 443, "protocol_hint": "TLS"},
        content_type="application/json",
    )
    target_id = created.json()["id"]

    patched = client.patch(
        f"/api/targets/{target_id}",
        data={"display_name": "   "},
        content_type="application/json",
    )

    assert created.status_code == 201
    assert created.json()["display_name"] == "Named Target"
    assert patched.status_code == 200
    assert patched.json()["target"]["display_name"] is None


def test_api_tgt_008_delete_target_soft_unlinks_assets(client):
    from apps.assets.models import Asset
    from apps.snapshots.models import CbomSnapshot
    from apps.targets.models import Target

    target = create_target()
    snapshot = CbomSnapshot.objects.create()
    asset = Asset.objects.create(snapshot=snapshot, target=target, name="web certificate")

    response = client.delete(f"/api/targets/{target.id}")

    assert response.status_code == 204
    assert not Target.objects.filter(id=target.id).exists()
    assert CbomSnapshot.objects.filter(id=snapshot.id).exists()
    assert Asset.objects.filter(id=asset.id).exists()
    asset.refresh_from_db()
    assert asset.snapshot_id == snapshot.id
    assert asset.target_id is None


def test_api_tgt_009_rejects_contract_invalid_target_fields(client):
    invalid_create = client.post(
        "/api/targets",
        data={
            "host": "bad.testbed.local",
            "ip": "not-an-ip",
            "port": 443,
            "protocol_hint": "FTP",
            "transport": "QUIC",
            "agent_url": "not-a-url",
            "context": {"criticality": "urgent", "exposure": "internet"},
        },
        content_type="application/json",
    )
    target = create_target()
    invalid_patch = client.patch(
        f"/api/targets/{target.id}",
        data={"protocol_hint": "FTP", "transport": "QUIC"},
        content_type="application/json",
    )

    assert invalid_create.status_code == 422
    assert invalid_create.json()["error"] == "unprocessable"
    assert invalid_patch.status_code == 422
