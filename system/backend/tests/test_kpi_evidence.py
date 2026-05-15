import json
from pathlib import Path

from apps.core.management.commands.seed_testbed_demo import (
    AGENT_FIXTURES,
    DEMO_DISCOVERY_RUNTIME_MINUTES,
    DEMO_FULL_PIPELINE_RUNTIME_MINUTES,
    DEMO_RECOMPUTE_RUNTIME_MINUTES,
    DEMO_SCAN_RUNTIME_MINUTES,
    DISCOVERY_ENDPOINTS,
    DORMANT_PRIVATE_KEY_PATHS,
    LATEST_ASSETS,
    SCAN_SCANNERS,
    TARGET_FIXTURE,
)
from apps.assets import services as asset_services
from apps.jobs.agent_asset_mapper import TYPE_SCANNER_KIND
from apps.meta.services import list_scanners
from migration_engine import recommend_migration
from risk_engine.llm import OPENAI_COMPATIBLE_PROVIDERS
from risk_engine.prompts import QUALITATIVE_RISK_PROMPT_VERSION, QUALITATIVE_RISK_RESPONSE_SCHEMA


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_BASELINE_PATH = REPO_ROOT / "docs" / "kpi" / "manual-grep-baseline.json"
HOST_AGENT_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "host-agent-evidence.json"
LLM_RISK_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "llm-risk-evidence.json"
OPEN_DEMO_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "open-demo-evidence.json"
RUNTIME_MINUTES_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "runtime-minutes-evidence.json"
STATIC_ANALYSIS_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "static-analysis-evidence.json"
MIGRATION_SCOPE_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "migration-scope-evidence.json"
CRYPTOSCAN_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "cryptoscan-evidence.json"


def test_manual_grep_baseline_scope_matches_demo_seed():
    evidence = json.loads(MANUAL_BASELINE_PATH.read_text())

    assert evidence["scope"]["asset_count"] == len(LATEST_ASSETS)
    assert evidence["scope"]["discovery_endpoint_count"] == len(DISCOVERY_ENDPOINTS)
    assert evidence["scope"]["host_agent_candidate_count"] == len(AGENT_FIXTURES)
    assert evidence["totals"]["presentation_label"] == "수일 ~ 수주"


def test_manual_grep_baseline_totals_match_step_sum():
    evidence = json.loads(MANUAL_BASELINE_PATH.read_text())
    min_hours = round(sum(step["min_hours"] for step in evidence["steps"]), 2)
    max_hours = round(sum(step["max_hours"] for step in evidence["steps"]), 2)
    work_hours_per_day = evidence["assumptions"]["work_hours_per_day"]

    assert evidence["totals"]["min_hours"] == min_hours
    assert evidence["totals"]["max_hours"] == max_hours
    assert evidence["totals"]["min_person_days"] == round(min_hours / work_hours_per_day, 2)
    assert evidence["totals"]["max_person_days"] == round(max_hours / work_hours_per_day, 2)
    assert evidence["totals"]["min_person_days"] >= 4
    assert evidence["totals"]["max_person_days"] >= 9


def test_host_agent_evidence_scope_matches_demo_seed():
    evidence = json.loads(HOST_AGENT_EVIDENCE_PATH.read_text())
    targets = json.loads(TARGET_FIXTURE.read_text())
    agent_scanners = [scanner for scanner in SCAN_SCANNERS if scanner.startswith("agent.")]
    agent_enabled_target_count = len([target for target in targets if target["fields"]["agent_enabled"]])

    assert evidence["scope"]["host_agent_count"] == len(AGENT_FIXTURES)
    assert evidence["scope"]["agent_enabled_target_count"] == agent_enabled_target_count
    assert evidence["scope"]["host_agent_scanner_count"] == len(agent_scanners)
    assert evidence["scope"]["expected_host_agent_run_log_count"] == agent_enabled_target_count * len(agent_scanners)
    assert evidence["scope"]["dormant_private_key_count"] == len(DORMANT_PRIVATE_KEY_PATHS)
    assert evidence["host_agent_scanners"] == agent_scanners


def test_host_agent_evidence_dormant_key_paths_match_demo_seed():
    evidence = json.loads(HOST_AGENT_EVIDENCE_PATH.read_text())
    by_ref = {item["bom_ref"]: item for item in evidence["dormant_private_key_assets"]}

    assert set(by_ref) == set(DORMANT_PRIVATE_KEY_PATHS)
    for bom_ref, paths in DORMANT_PRIVATE_KEY_PATHS.items():
        assert by_ref[bom_ref]["paths"] == paths
        assert by_ref[bom_ref]["source_scanner"] == "agent.private_key_files"
    assert evidence["safety"]["private_key_plaintext_stored"] is False


def test_llm_risk_evidence_matches_provider_and_prompt_contract():
    evidence = json.loads(LLM_RISK_EVIDENCE_PATH.read_text())

    assert evidence["flow"]["task_name"] == asset_services.QUALITATIVE_TASK_NAME
    assert evidence["flow"]["prompt_version"] == QUALITATIVE_RISK_PROMPT_VERSION
    assert evidence["flow"]["provider_mode"] in OPENAI_COMPATIBLE_PROVIDERS
    assert evidence["flow"]["fallback_provider"] == asset_services.QUALITATIVE_FALLBACK_PROVIDER
    assert evidence["flow"]["default_provider"] == asset_services.QUALITATIVE_PROVIDER
    assert evidence["required_response_fields"] == list(QUALITATIVE_RISK_RESPONSE_SCHEMA)
    assert evidence["dhs_criteria"] == list(QUALITATIVE_RISK_RESPONSE_SCHEMA["dhs_criteria"])
    assert evidence["provider_request"]["endpoint_suffix"] == "/chat/completions"
    assert evidence["provider_request"]["json_mode"] is True
    assert evidence["safety"]["fallback_on_provider_error"] is True
    assert evidence["safety"]["fallback_on_parse_error"] is True
    assert evidence["safety"]["prompt_cache_enabled"] is True


def test_open_demo_evidence_records_public_repo_and_live_dashboard_checks():
    evidence = json.loads(OPEN_DEMO_EVIDENCE_PATH.read_text())
    checks = evidence["checks"]

    assert checks["github_repository"]["url"] == "https://github.com/ehdgks0627/crypto-scanner"
    assert checks["github_repository"]["http_status"] == 200
    assert checks["github_repository"]["repository_public"] is True
    assert checks["github_raw_readme"]["http_status"] == 200
    assert checks["live_health"]["url"] == "https://pqc.sprout.kr/api/health"
    assert checks["live_health"]["http_status"] == 200
    assert checks["live_health"]["response"] == {
        "status": "ok",
        "api": "ok",
        "database": "ok",
        "redis": "ok",
        "worker": "ok",
    }
    assert checks["live_dashboard"]["url"] == "https://pqc.sprout.kr/dashboard"
    assert checks["live_dashboard"]["http_status"] == 200
    assert checks["live_dashboard"]["page_title"] == "PQC Risk Assessment"
    assert any("deployment freshness" in limitation for limitation in evidence["limitations"])


def test_runtime_minutes_evidence_matches_demo_seed_constants():
    evidence = json.loads(RUNTIME_MINUTES_EVIDENCE_PATH.read_text())
    measurements = evidence["measurements"]

    assert evidence["scenario"] == "testbed_demo"
    assert measurements["discovery_runtime_minutes"]["value"] == DEMO_DISCOVERY_RUNTIME_MINUTES
    assert measurements["automated_inventory_runtime_minutes_per_scan"]["value"] == DEMO_SCAN_RUNTIME_MINUTES
    assert measurements["risk_recompute_runtime_minutes"]["value"] == DEMO_RECOMPUTE_RUNTIME_MINUTES
    assert measurements["full_pipeline_runtime_minutes"]["value"] == DEMO_FULL_PIPELINE_RUNTIME_MINUTES
    assert measurements["full_pipeline_runtime_minutes"]["threshold_minutes"] == 10
    assert measurements["full_pipeline_runtime_minutes"]["passed"] is True
    assert DEMO_FULL_PIPELINE_RUNTIME_MINUTES <= 10


def test_static_analysis_evidence_is_limited_to_file_and_config_inspection():
    evidence = json.loads(STATIC_ANALYSIS_EVIDENCE_PATH.read_text())
    available_scanners = {scanner["id"] for scanner in list_scanners()}
    supported_scanners = {item["scanner"] for item in evidence["supported_static_inputs"]}

    assert evidence["comparison_mark"] == "△"
    assert evidence["claim_level"] == "partial"
    assert supported_scanners <= available_scanners
    assert supported_scanners <= {scanner for scanner in SCAN_SCANNERS if scanner.startswith("agent.")}
    assert set(evidence["mapped_finding_types"]) == set(TYPE_SCANNER_KIND)
    assert "generic source-code repository scanning" in evidence["unsupported_static_analysis"]
    assert "language-level crypto API dataflow analysis" in evidence["unsupported_static_analysis"]


def test_migration_scope_evidence_is_recommendation_only():
    evidence = json.loads(MIGRATION_SCOPE_EVIDENCE_PATH.read_text())
    recommendation = recommend_migration(
        asset_id=1,
        asset_name="web.testbed.local certificate",
        asset_type="certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        risk_score=82,
        tier="CRITICAL",
        context={"exposure": "public_internet", "criticality": "high"},
        capabilities={"inventory_fresh", "owner_known"},
    )
    endpoint_methods = {endpoint["method"] for endpoint in evidence["api_endpoints"]}

    assert evidence["comparison_mark"] == "△"
    assert evidence["claim_level"] == "recommendation_only"
    assert set(evidence["implemented_outputs"]) <= set(recommendation)
    assert recommendation["recommendation"]["target_algorithm"]
    assert endpoint_methods == {"GET"}
    assert "actual key replacement automation" in evidence["unsupported_execution"]
    assert "service configuration file mutation" in evidence["unsupported_execution"]


def test_cryptoscan_evidence_classifies_tool_as_codebase_static_scanner():
    evidence = json.loads(CRYPTOSCAN_EVIDENCE_PATH.read_text())
    supported_scope = set(evidence["supported_scope"])
    unsupported_scope = set(evidence["not_evidenced_as"])
    source_urls = [item["url"] for item in evidence["official_evidence"]]

    assert evidence["claim_level"] == "fact_checked"
    assert evidence["repository"] == "https://github.com/csnp/cryptoscan"
    assert evidence["observed_commit"]
    assert evidence["scope_label"] == "codebase_configuration_dependency_static_scanning"
    assert "remote Git repository scanning by cloning to a temporary directory" in supported_scope
    assert "dependency manifest scanning" in supported_scope
    assert "SARIF output" in supported_scope
    assert "CBOM output" in supported_scope
    assert "active network endpoint discovery" in unsupported_scope
    assert "TLS handshake scanner" in unsupported_scope
    assert all(evidence["observed_commit"] in url for url in source_urls)
