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


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_BASELINE_PATH = REPO_ROOT / "docs" / "kpi" / "manual-grep-baseline.json"
HOST_AGENT_EVIDENCE_PATH = REPO_ROOT / "docs" / "kpi" / "host-agent-evidence.json"


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
