from collections import Counter
from dataclasses import replace
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.agents.models import Agent
from apps.agents.services import is_stale
from apps.assets.models import Asset
from apps.jobs import agent_client, network_scanner
from apps.jobs.agent_asset_mapper import map_agent_findings
from apps.jobs.models import AsyncJob, QueuedTask, ScanRunLog
from apps.risk import services as risk_services
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


AGENT_SCANNER_PREFIX = "agent."


def process_next_scan_job_task() -> dict | None:
    task = (
        QueuedTask.objects.filter(task_name="scan_job", status=QueuedTask.QUEUED, available_at__lte=timezone.now())
        .order_by("available_at", "id")
        .first()
    )
    if not task:
        return None
    return process_scan_job_task(task.id)


def process_scan_job_task(task_id: int) -> dict:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        if task.status == QueuedTask.CANCELLED:
            return {}
        if task.status != QueuedTask.QUEUED:
            raise ValueError(f"QueuedTask {task.id} is not queued")
        async_job = task.async_job
        scan_job = async_job.scan_job
        total = len(scan_job.target_ids) * len(scan_job.scanner_selection)
        now = timezone.now()
        task.status = QueuedTask.RUNNING
        task.attempts += 1
        task.locked_at = now
        task.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        if async_job.status == AsyncJob.CANCELLED:
            task.status = QueuedTask.CANCELLED
            task.save(update_fields=["status", "updated_at"])
            return {}
        async_job.status = AsyncJob.RUNNING
        async_job.started_at = async_job.started_at or now
        async_job.progress = {"completed": 0, "total": total, "current_target": None, "current_scanner": None}
        async_job.save(update_fields=["status", "started_at", "progress", "updated_at"])

    try:
        result = run_scan_job_payload(task.payload)
    except Exception as exc:
        _fail_scan_job_task(task_id, exc)
        raise

    _complete_scan_job_task(task_id, result)
    return result


def run_scan_job_payload(payload: dict) -> dict:
    from apps.jobs.models import ScanJob

    scan_job = ScanJob.objects.select_related("async_job").get(id=payload["scan_job_id"])
    target_ids = list(payload.get("target_ids") or scan_job.target_ids)
    scanners = list(payload.get("scanners") or scan_job.scanner_selection)
    targets = _targets_for_ids(target_ids)
    candidates = []
    completed = 0
    total = len(targets) * len(scanners)

    for target in targets:
        if "network" in scanners:
            candidates.extend(_run_network_scanner(scan_job.async_job, target))
            completed += 1
            _update_progress(scan_job.async_job_id, completed, total, target, "network")

        agent_scanners = [scanner for scanner in scanners if scanner.startswith(AGENT_SCANNER_PREFIX)]
        if agent_scanners:
            agent_candidates, completed = _run_agent_scanners(scan_job.async_job, target, agent_scanners, completed, total)
            candidates.extend(agent_candidates)

    snapshot = _persist_snapshot(scan_job, candidates)
    risk_result = risk_services.recompute_snapshot_risks(snapshot.id)
    return {
        "scan_job_id": scan_job.id,
        "snapshot_id": snapshot.id,
        "snapshot_serial": snapshot.serial_number,
        "assets_count": snapshot.assets.count(),
        "risk_scores_count": risk_result["updated_scores_count"],
    }


def _targets_for_ids(target_ids: list[int]) -> list[Target]:
    targets_by_id = {target.id: target for target in Target.objects.filter(id__in=target_ids)}
    missing = [target_id for target_id in target_ids if target_id not in targets_by_id]
    if missing:
        raise ValueError(f"scan target not found: {missing}")
    return [targets_by_id[target_id] for target_id in target_ids]


def _run_network_scanner(async_job, target) -> list:
    started_at = timezone.now()
    try:
        candidates = network_scanner.scan_network_target(target)
    except Exception as exc:
        ScanRunLog.objects.create(
            async_job=async_job,
            target=target,
            scanner_kind="network",
            status="ERROR",
            findings_count=0,
            started_at=started_at,
            finished_at=timezone.now(),
            error=str(exc)[:128],
        )
        return []
    ScanRunLog.objects.create(
        async_job=async_job,
        target=target,
        scanner_kind="network",
        status="SUCCESS",
        findings_count=len(candidates),
        started_at=started_at,
        finished_at=timezone.now(),
    )
    return candidates


def _run_agent_scanners(async_job, target, scanner_kinds: list[str], completed: int, total: int):
    supported_scanners, skip_errors = _supported_agent_scanners(target, scanner_kinds)
    for scanner_kind, error in skip_errors.items():
        ScanRunLog.objects.create(
            async_job=async_job,
            target=target,
            scanner_kind=scanner_kind,
            status="SKIPPED",
            findings_count=0,
            started_at=timezone.now(),
            finished_at=timezone.now(),
            error=error,
        )
        completed += 1
        _update_progress(async_job.id, completed, total, target, scanner_kind)

    if not supported_scanners:
        return [], completed

    agent = Agent.objects.get(hostname=target.host, agent_role=Agent.ROLE_HOST, active=True)
    started_at = timezone.now()
    try:
        response = agent_client.post_scan(agent, supported_scanners)
        candidates = map_agent_findings(target, response.get("findings", []), set(supported_scanners))
    except Exception as exc:
        candidates = []
        error = str(exc)[:128]
        for scanner_kind in supported_scanners:
            ScanRunLog.objects.create(
                async_job=async_job,
                target=target,
                scanner_kind=scanner_kind,
                status="ERROR",
                findings_count=0,
                started_at=started_at,
                finished_at=timezone.now(),
                error=error,
            )
            completed += 1
            _update_progress(async_job.id, completed, total, target, scanner_kind)
        return [], completed

    counts = Counter(candidate.scanner_kind for candidate in candidates)
    for scanner_kind in supported_scanners:
        ScanRunLog.objects.create(
            async_job=async_job,
            target=target,
            scanner_kind=scanner_kind,
            status="SUCCESS",
            findings_count=counts.get(scanner_kind, 0),
            started_at=started_at,
            finished_at=timezone.now(),
        )
        completed += 1
        _update_progress(async_job.id, completed, total, target, scanner_kind)
    return candidates, completed


def _supported_agent_scanners(target, scanner_kinds: list[str]) -> tuple[list[str], dict[str, str]]:
    if not target.agent_enabled:
        return [], {scanner_kind: "agent_disabled" for scanner_kind in scanner_kinds}
    agent = Agent.objects.filter(hostname=target.host, agent_role=Agent.ROLE_HOST, active=True).first()
    if not agent:
        return [], {scanner_kind: "agent_unavailable" for scanner_kind in scanner_kinds}
    if is_stale(agent):
        return [], {scanner_kind: "agent_stale" for scanner_kind in scanner_kinds}
    if not agent.agent_url or not agent.agent_runtime_token:
        return [], {scanner_kind: "agent_unavailable" for scanner_kind in scanner_kinds}

    supported = [scanner_kind for scanner_kind in scanner_kinds if scanner_kind in agent.capabilities]
    skipped = {scanner_kind: "capability_unsupported" for scanner_kind in scanner_kinds if scanner_kind not in agent.capabilities}
    return supported, skipped


def _persist_snapshot(scan_job, candidates: list) -> CbomSnapshot:
    unique_candidates = _dedupe_candidates(candidates)
    snapshot = CbomSnapshot.objects.create(
        scan_job=scan_job,
        serial_number=f"urn:uuid:{uuid4()}",
        summary=_snapshot_summary(unique_candidates),
        validation_errors=[],
    )
    for candidate in unique_candidates:
        Asset.objects.create(
            snapshot=snapshot,
            target_id=candidate.target_id,
            name=candidate.name[:255],
            asset_class="crypto",
            asset_type=candidate.asset_type[:32],
            bom_ref=candidate.bom_ref[:255],
            algorithm=candidate.algorithm[:128],
            algorithm_family=candidate.algorithm_family[:64],
            metadata=candidate.metadata or {},
        )
    return snapshot


def _dedupe_candidates(candidates: list):
    by_ref = {}
    for candidate in candidates:
        key = _dedupe_key(candidate)
        if key in by_ref:
            by_ref[key] = _merge_candidates(by_ref[key], candidate)
        else:
            by_ref[key] = candidate
    return list(by_ref.values())


def _dedupe_key(candidate) -> str:
    metadata = candidate.metadata or {}
    fingerprint = metadata.get("fingerprint_sha256")
    if fingerprint:
        return f"{candidate.asset_type}:fingerprint:{str(fingerprint).lower()}"
    return f"bom_ref:{candidate.bom_ref}"


def _merge_candidates(existing, incoming):
    existing_metadata = dict(existing.metadata or {})
    incoming_metadata = dict(incoming.metadata or {})
    merged_metadata = {**incoming_metadata, **existing_metadata}
    source_scanners = _merged_values(existing_metadata.get("source_scanners"), existing_metadata.get("scanner") or existing.scanner_kind)
    source_scanners = _merged_values(source_scanners, incoming_metadata.get("source_scanners"))
    source_scanners = _merged_values(source_scanners, incoming_metadata.get("scanner") or incoming.scanner_kind)
    source_paths = _merged_values(existing_metadata.get("source_paths"), existing_metadata.get("path"))
    source_paths = _merged_values(source_paths, incoming_metadata.get("source_paths"))
    source_paths = _merged_values(source_paths, incoming_metadata.get("path"))
    source_bom_refs = _merged_values(existing_metadata.get("source_bom_refs"), existing.bom_ref)
    source_bom_refs = _merged_values(source_bom_refs, incoming_metadata.get("source_bom_refs"))
    source_bom_refs = _merged_values(source_bom_refs, incoming.bom_ref)

    merged_metadata["source_scanners"] = source_scanners
    merged_metadata["source_bom_refs"] = source_bom_refs
    if source_paths:
        merged_metadata["source_paths"] = source_paths
    if len(source_scanners) > 1:
        merged_metadata["scanner"] = "multiple"
        merged_metadata["merged"] = True
    return replace(existing, metadata=merged_metadata)


def _merged_values(current, value):
    result = []
    for item in _as_list(current) + _as_list(value):
        if item is None or item == "":
            continue
        if item not in result:
            result.append(item)
    return result


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _snapshot_summary(candidates: list) -> dict:
    by_type = Counter(candidate.asset_type for candidate in candidates)
    by_algorithm_family = Counter(candidate.algorithm_family or "unknown" for candidate in candidates)
    by_scanner = Counter(candidate.scanner_kind for candidate in candidates)
    return {
        "asset_count": len(candidates),
        "target_count": len({candidate.target_id for candidate in candidates}),
        "by_type": dict(sorted(by_type.items())),
        "by_algorithm_family": dict(sorted(by_algorithm_family.items())),
        "by_scanner": dict(sorted(by_scanner.items())),
    }


def _update_progress(async_job_id: int, completed: int, total: int, target, scanner_kind: str) -> None:
    AsyncJob.objects.filter(id=async_job_id).update(
        progress={
            "completed": completed,
            "total": total,
            "current_target": f"{target.host}:{target.port}",
            "current_scanner": scanner_kind,
        },
        updated_at=timezone.now(),
    )


def _complete_scan_job_task(task_id: int, result: dict) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        if task.async_job.status == AsyncJob.CANCELLED:
            task.status = QueuedTask.CANCELLED
            task.save(update_fields=["status", "updated_at"])
            return
        task.status = QueuedTask.COMPLETED
        task.last_error = None
        task.save(update_fields=["status", "last_error", "updated_at"])
        async_job = task.async_job
        async_job.status = AsyncJob.COMPLETED
        async_job.progress = {
            "completed": async_job.progress.get("total", 0) if async_job.progress else 0,
            "total": async_job.progress.get("total", 0) if async_job.progress else 0,
            "current_target": None,
            "current_scanner": None,
        }
        async_job.result = result
        async_job.error = None
        async_job.finished_at = timezone.now()
        async_job.save(update_fields=["status", "progress", "result", "error", "finished_at", "updated_at"])


def _fail_scan_job_task(task_id: int, exc: Exception) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        task.status = QueuedTask.FAILED
        task.last_error = str(exc)
        task.save(update_fields=["status", "last_error", "updated_at"])
        async_job = task.async_job
        async_job.status = AsyncJob.FAILED
        async_job.error = {"message": str(exc)}
        async_job.finished_at = timezone.now()
        async_job.save(update_fields=["status", "error", "finished_at", "updated_at"])
