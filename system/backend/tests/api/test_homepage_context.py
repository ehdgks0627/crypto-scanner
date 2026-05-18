import pytest

from apps.jobs.scan_worker import _apply_homepage_context_inference
from tests.api.factories import create_target


pytestmark = pytest.mark.django_db


def test_scan_worker_applies_homepage_context_to_empty_target_fields():
    target = create_target(
        context={
            "sensitivity": None,
            "lifespan_years": None,
            "criticality": None,
            "exposure": None,
            "service_role": None,
        }
    )

    _apply_homepage_context_inference(
        target,
        {
            "service_role": "authentication",
            "sensitivity": "high",
            "criticality": "high",
            "exposure": "dmz",
            "lifespan_years": 10,
            "homepage_inference": {
                "source": "homepage",
                "method": "html_keyword_inference",
                "url": "https://auth.testbed.local:443/",
                "title": "Identity Login",
                "signals": ["login", "oidc", "mfa"],
                "confidence": 0.84,
            },
        },
    )

    target.refresh_from_db()
    assert target.context["service_role"] == "authentication"
    assert target.context["sensitivity"] == "high"
    assert target.context["criticality"] == "high"
    assert target.context["exposure"] == "dmz"
    assert target.context["lifespan_years"] == 10
    assert target.context["homepage_inference"]["applied_fields"] == [
        "sensitivity",
        "lifespan_years",
        "criticality",
        "exposure",
        "service_role",
    ]


def test_scan_worker_keeps_manual_context_and_records_homepage_evidence():
    target = create_target(
        context={
            "sensitivity": "critical",
            "lifespan_years": 7,
            "criticality": "high",
            "exposure": "internal_network",
            "service_role": "manual-role",
        }
    )

    _apply_homepage_context_inference(
        target,
        {
            "service_role": "public_web",
            "sensitivity": "medium",
            "criticality": "medium",
            "exposure": "dmz",
            "lifespan_years": 3,
            "homepage_inference": {
                "source": "homepage",
                "method": "html_keyword_inference",
                "url": "https://web.testbed.local:443/",
                "title": "Welcome",
                "signals": ["welcome"],
                "confidence": 0.58,
            },
        },
    )

    target.refresh_from_db()
    assert target.context["service_role"] == "manual-role"
    assert target.context["sensitivity"] == "critical"
    assert target.context["exposure"] == "internal_network"
    assert target.context["homepage_inference"]["title"] == "Welcome"
    assert target.context["homepage_inference"]["applied_fields"] == []
