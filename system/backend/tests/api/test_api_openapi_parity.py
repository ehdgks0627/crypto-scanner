import re
from pathlib import Path


def _normalize_path(path: str) -> str:
    normalized = re.sub(r"\{[^}]+\}", "{id}", path)
    return normalized.removeprefix("/api")


def test_pr_openapi_001_generated_schema_covers_static_contract_paths(client):
    contract = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.yaml"
    contract_paths = {
        _normalize_path(match.group(1))
        for match in re.finditer(r"^  (/[^:\n]+):", contract.read_text(), re.MULTILINE)
    }
    generated_paths = {
        _normalize_path(path)
        for path in client.get("/api/openapi.json").json()["paths"]
    }

    assert contract_paths <= generated_paths


def test_pr_openapi_002_recent_contract_schema_fields_are_declared():
    contract = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.yaml"
    text = contract.read_text()

    assert "required: [id, job_id, scope_type, scope_value, cidr, executor_type, agent_id, agent_hostname, port_list, status, created_at, started_at]" in text
    assert "scan_job_id:\n          type: integer\n          nullable: true" in text
    assert "quantum_vulnerable_ratio:" in text
    assert "application/*+json" not in text
    assert "'422':\n          $ref: '#/components/responses/Unprocessable'" in text
    assert "AssetContextPatchResult:" in text
    assert "applied_overrides:" in text
    assert "ApiToken:" in text
    assert "name: X-API-Token" in text
    assert "maximum: 100" in text
    assert "DiscoveryAvailabilityReport:" in text
    assert "availability_metrics:" in text
