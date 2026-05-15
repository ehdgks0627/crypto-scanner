import json
from pathlib import Path

from apps.core.management.commands.seed_testbed_demo import AGENT_FIXTURES, DISCOVERY_ENDPOINTS, LATEST_ASSETS


REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_BASELINE_PATH = REPO_ROOT / "docs" / "kpi" / "manual-grep-baseline.json"


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
