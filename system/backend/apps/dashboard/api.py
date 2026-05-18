from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO

from django.core.management import call_command
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ninja import Router
from pydantic import Field

from apps.agents.models import Agent
from apps.agents.services import is_stale
from apps.core.management.commands.seed_testbed_demo import LATEST_ASSETS, SERIAL_PREFIX
from apps.core.schemas import StrictSchema
from apps.jobs.models import AsyncJob
from apps.jobs.services import serialize_dt, serialize_job
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


router = Router(tags=["Dashboard"])


VULNERABLE_ALGORITHM_FAMILIES = {"RSA", "ECDSA", "ECDH", "DH"}
EXPIRING_CERTIFICATE_WINDOW_DAYS = 90
CERTIFICATE_EXPIRY_KEYS = ("expires_at", "not_after", "valid_to", "valid_until", "expiration")
PRIVATE_KEY_ASSET_TYPES = {"key", "ssh_user_key", "keystore_entry", "package_key"}
PIPELINE_JOB_KINDS = ("discovery", "recompute")


class DemoSeedPayload(StrictSchema):
    reset: bool = Field(default=True)


@router.get("/dashboard/summary")
def get_dashboard_summary(request, snapshot_id: int | None = None):
    latest = CbomSnapshot.objects.filter(id=snapshot_id).first() if snapshot_id else CbomSnapshot.objects.order_by("-id").first()
    agents = list(Agent.objects.all())
    agent_status = {
        "total": len(agents),
        "active": len([agent for agent in agents if agent.active]),
        "stale": len([agent for agent in agents if agent.active and is_stale(agent)]),
    }
    recent_jobs = [serialize_job(job) for job in AsyncJob.objects.order_by("-id")[:5]]

    if latest is None:
        return {
            "snapshot": None,
            "by_tier": {},
            "by_asset_type": {},
            "by_algorithm_family": {},
            "quantum_vulnerable_ratio": {"vulnerable": 0, "safe": 0, "unknown": 0},
            "kpis": _dashboard_kpis(None, [], 0, 0, 0, 0, 0),
            "recent_jobs": recent_jobs,
            "agents_status": agent_status,
            "trend": [],
            "context_inferences": [],
        }

    risk_scores = list(RiskScore.objects.filter(snapshot=latest).select_related("asset"))
    assets = list(latest.assets.all())
    by_tier = {}
    by_asset_type = {}
    by_algorithm_family = {}
    vulnerable_count = 0
    for risk_score in risk_scores:
        by_tier[risk_score.tier] = by_tier.get(risk_score.tier, 0) + 1
    for asset in assets:
        by_asset_type[asset.asset_type] = by_asset_type.get(asset.asset_type, 0) + 1
        family = asset.algorithm_family or "UNKNOWN"
        by_algorithm_family[family] = by_algorithm_family.get(family, 0) + 1
        if asset.algorithm_family in VULNERABLE_ALGORITHM_FAMILIES:
            vulnerable_count += 1
    known_count = len([asset for asset in assets if asset.algorithm_family])
    safe_count = max(known_count - vulnerable_count, 0)
    unknown_count = max(len(assets) - known_count, 0)
    trend = []
    for snapshot in CbomSnapshot.objects.order_by("-created_at")[:10]:
        trend_scores = RiskScore.objects.filter(snapshot=snapshot)
        trend.append(
            {
                "snapshot_id": snapshot.id,
                "created_at": serialize_dt(snapshot.created_at),
                "critical_count": trend_scores.filter(tier="CRITICAL").count(),
                "total_count": snapshot.assets.count(),
            }
        )
    trend.reverse()
    automated_runtime_minutes = _snapshot_scan_duration_minutes(latest)
    pipeline_runtime_minutes = _pipeline_runtime_minutes(latest, automated_runtime_minutes)
    return {
        "snapshot": {
            "id": latest.id,
            "created_at": serialize_dt(latest.created_at),
            "asset_count": len(assets),
        },
        "by_tier": by_tier,
        "by_asset_type": by_asset_type,
        "by_algorithm_family": by_algorithm_family,
        "quantum_vulnerable_ratio": {
            "vulnerable": vulnerable_count,
            "safe": safe_count,
            "unknown": unknown_count,
        },
        "kpis": _dashboard_kpis(
            latest,
            assets,
            vulnerable_count,
            _expiring_certificate_count(assets),
            _dormant_private_key_count(assets),
            automated_runtime_minutes,
            pipeline_runtime_minutes,
        ),
        "recent_jobs": recent_jobs,
        "agents_status": agent_status,
        "trend": trend,
        "context_inferences": _homepage_context_inferences(assets),
    }


@router.post("/dashboard/demo-seed")
def seed_dashboard_demo(request, payload: DemoSeedPayload):
    stdout = StringIO()
    args = ["--reset"] if payload.reset else []
    call_command("seed_testbed_demo", *args, stdout=stdout)

    latest = CbomSnapshot.objects.filter(serial_number=f"{SERIAL_PREFIX}-latest").order_by("-id").first()
    baseline = CbomSnapshot.objects.filter(serial_number=f"{SERIAL_PREFIX}-baseline").order_by("-id").first()
    return JsonResponse(
        {
            "status": "loaded",
            "reset": payload.reset,
            "scenario": "testbed_demo",
            "latest_snapshot_id": latest.id if latest else None,
            "baseline_snapshot_id": baseline.id if baseline else None,
            "asset_count": latest.assets.count() if latest else len(LATEST_ASSETS),
            "message": stdout.getvalue().strip(),
        },
        status=201,
    )


def _dashboard_kpis(
    snapshot: CbomSnapshot | None,
    assets: list,
    vulnerable_count: int,
    expiring_certificate_count: int,
    dormant_private_key_count: int,
    automated_runtime_minutes: int,
    pipeline_runtime_minutes: int,
) -> dict:
    return {
        "discovered_crypto_assets_per_scan": {
            "value": len(assets),
            "unit": "assets",
            "source": "cbom_snapshot",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        },
        "quantum_vulnerable_assets_per_scan": {
            "value": vulnerable_count,
            "unit": "assets",
            "source": "algorithm_family_classification",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        },
        "expiring_certificates_90d_per_scan": {
            "value": expiring_certificate_count,
            "unit": "certificates",
            "source": "certificate_metadata_expires_at",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        },
        "dormant_private_keys_per_scan": {
            "value": dormant_private_key_count,
            "unit": "keys",
            "source": "asset_metadata_dormant_private_key",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        },
        "automated_inventory_runtime_minutes_per_scan": {
            "value": automated_runtime_minutes,
            "unit": "minutes",
            "source": "scan_job_timestamps",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        },
        "full_pipeline_runtime_minutes": {
            "value": pipeline_runtime_minutes,
            "unit": "minutes",
            "source": "pipeline_job_timestamps",
            "snapshot_id": snapshot.id if snapshot else None,
            "scan_job_id": snapshot.scan_job_id if snapshot else None,
        }
    }


def _expiring_certificate_count(assets: list, now=None) -> int:
    now = now or timezone.now()
    deadline = now + timedelta(days=EXPIRING_CERTIFICATE_WINDOW_DAYS)
    count = 0
    for asset in assets:
        if asset.asset_type != "certificate":
            continue
        expires_at = _asset_expiration(asset)
        if expires_at and now <= expires_at <= deadline:
            count += 1
    return count


def _asset_expiration(asset) -> datetime | None:
    metadata = asset.metadata or {}
    containers = [metadata]
    for key in ("summary", "certificate", "validity"):
        value = metadata.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in CERTIFICATE_EXPIRY_KEYS:
            parsed = _parse_expiration_datetime(container.get(key))
            if parsed:
                return parsed
    return None


def _parse_expiration_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        parsed = parse_datetime(text)
        if parsed is None:
            for fmt in ("%b %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y GMT"):
                try:
                    parsed = datetime.strptime(text, fmt).replace(tzinfo=dt_timezone.utc)
                    break
                except ValueError:
                    continue
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _dormant_private_key_count(assets: list) -> int:
    return len([asset for asset in assets if _is_dormant_private_key(asset)])


def _is_dormant_private_key(asset) -> bool:
    metadata = asset.metadata or {}
    if asset.asset_type not in PRIVATE_KEY_ASSET_TYPES:
        return False
    if not _has_private_key_file_evidence(metadata):
        return False
    dormant = _metadata_bool(metadata.get("dormant"))
    in_use = _metadata_bool(metadata.get("in_use"))
    return dormant is True or in_use is False


def _homepage_context_inferences(assets: list) -> list[dict]:
    target_ids = sorted({asset.target_id for asset in assets if asset.target_id})
    if not target_ids:
        return []
    targets = Target.objects.filter(id__in=target_ids).order_by("host", "port")
    rows = []
    for target in targets:
        context = target.context if isinstance(target.context, dict) else {}
        inference = context.get("homepage_inference")
        if not isinstance(inference, dict):
            continue
        rows.append(
            {
                "target_id": target.id,
                "target_label": f"{target.host}:{target.port}",
                "service_role": context.get("service_role"),
                "sensitivity": context.get("sensitivity"),
                "criticality": context.get("criticality"),
                "exposure": context.get("exposure"),
                "lifespan_years": context.get("lifespan_years"),
                "confidence": inference.get("confidence"),
                "title": inference.get("title"),
                "description": inference.get("description"),
                "signals": inference.get("signals") or [],
                "url": inference.get("url"),
            }
        )
    rows.sort(key=lambda item: (-(item["confidence"] or 0), item["target_label"]))
    return rows[:6]


def _has_private_key_file_evidence(metadata: dict) -> bool:
    if metadata.get("private_key_paths"):
        return True
    evidence_values = [
        metadata.get("scanner"),
        metadata.get("type"),
        metadata.get("path"),
        metadata.get("source_scanners"),
        metadata.get("source_paths"),
    ]
    for value in evidence_values:
        if isinstance(value, list):
            if any("private_key" in str(item).casefold() for item in value):
                return True
        elif "private_key" in str(value or "").casefold():
            return True
    return False


def _metadata_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _snapshot_scan_duration_minutes(snapshot: CbomSnapshot | None) -> int:
    if snapshot is None or snapshot.scan_job_id is None:
        return 0
    async_job = snapshot.scan_job.async_job
    return _duration_minutes(async_job.started_at, async_job.finished_at)


def _pipeline_runtime_minutes(snapshot: CbomSnapshot | None, scan_runtime_minutes: int) -> int:
    if snapshot is None or snapshot.scan_job_id is None:
        return 0
    scenario = (snapshot.scan_job.async_job.request_payload or {}).get("scenario")
    if not scenario:
        return scan_runtime_minutes
    return scan_runtime_minutes + sum(_latest_completed_job_duration_minutes(scenario, kind) for kind in PIPELINE_JOB_KINDS)


def _latest_completed_job_duration_minutes(scenario: str, kind: str) -> int:
    job = (
        AsyncJob.objects.filter(
            kind=kind,
            status=AsyncJob.COMPLETED,
            request_payload__scenario=scenario,
            started_at__isnull=False,
            finished_at__isnull=False,
        )
        .order_by("-finished_at", "-id")
        .first()
    )
    if job is None:
        return 0
    return _duration_minutes(job.started_at, job.finished_at)


def _duration_minutes(started_at, finished_at) -> int:
    if not started_at or not finished_at or finished_at < started_at:
        return 0
    seconds = (finished_at - started_at).total_seconds()
    minutes = int(round(seconds / 60))
    if seconds > 0 and minutes == 0:
        return 1
    return minutes
