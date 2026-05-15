import json
from pathlib import Path

from apps.core.management.commands.seed_testbed_demo import (
    AGENT_FIXTURES,
    DISCOVERY_ENDPOINTS,
    DORMANT_PRIVATE_KEY_PATHS,
    LATEST_ASSETS,
    SCAN_SCANNERS,
    TARGET_FIXTURE,
)
from apps.assets import services as asset_services
from risk_engine.llm import OPENAI_COMPATIBLE_PROVIDERS
from risk_engine.prompts import QUALITATIVE_RISK_PROMPT_VERSION, QUALITATIVE_RISK_RESPONSE_SCHEMA


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_BASELINE_PATH = REPO_ROOT / "docs" / "kpi" / "manual-grep-baseline.json"
HOST_AGENT_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "host-agent-evidence.json"
LLM_RISK_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "llm-risk-evidence.json"
OPEN_DEMO_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "open-demo-evidence.json"


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
