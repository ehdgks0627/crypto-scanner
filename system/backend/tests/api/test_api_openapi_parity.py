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
