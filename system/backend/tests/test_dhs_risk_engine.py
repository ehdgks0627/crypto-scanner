from risk_engine import DHS_CRITERION_WEIGHTS, compute_dhs_risk, priority_for_dhs_score


def test_compute_dhs_risk_weights_all_six_criteria_with_hndl_highest():
    result = compute_dhs_risk(
        {
            "asset_value": {"score": 0.8, "rating": "high"},
            "protected_information": {"score": 0.9, "rating": "critical"},
            "communication_scope": {"score": 0.7, "rating": "high"},
            "sharing_level": {"score": 0.5, "rating": "medium"},
            "critical_infrastructure": {"score": 0.85, "rating": "critical"},
            "protection_duration": {"score": 1.0, "rating": "critical"},
        }
    )

    assert result.score_10 == 8.2
    assert result.priority == "P1"
    assert result.missing_criteria == []
    assert result.weights["protection_duration"] == max(result.weights.values())
    assert result.criteria["protection_duration"]["weighted_score"] == 1.6
    assert DHS_CRITERION_WEIGHTS["protection_duration"] > DHS_CRITERION_WEIGHTS["critical_infrastructure"]


def test_compute_dhs_risk_falls_back_to_rating_and_tracks_missing_criteria():
    result = compute_dhs_risk(
        {
            "asset_value": {"rating": "MEDIUM"},
            "protection_duration": {"rating": "HIGH"},
        }
    )

    assert result.score_10 == 2.5
    assert result.priority == "P3"
    assert set(result.missing_criteria) == {
        "protected_information",
        "communication_scope",
        "sharing_level",
        "critical_infrastructure",
    }
    assert result.criteria["asset_value"]["score"] == 0.5
    assert result.criteria["protection_duration"]["score"] == 0.75


def test_priority_for_dhs_score_thresholds():
    assert priority_for_dhs_score(8.0) == "P1"
    assert priority_for_dhs_score(5.0) == "P2"
    assert priority_for_dhs_score(4.9) == "P3"
