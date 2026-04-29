from datetime import UTC

from django.utils import timezone

from apps.jobs.models import QueuedTask


class EnqueueUnavailable(Exception):
    pass


def serialize_dt(value):
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_job(async_job):
    resource_id = async_job.resource_id or async_job.id
    return {
        "id": async_job.id,
        "kind": async_job.kind,
        "resource": {"kind": async_job.kind, "id": resource_id},
        "status": async_job.status,
        "progress": async_job.progress,
        "started_at": serialize_dt(async_job.started_at),
        "cancel_requested_at": serialize_dt(async_job.cancel_requested_at),
        "finished_at": serialize_dt(async_job.finished_at),
        "result": async_job.result,
        "error": async_job.error,
    }


def serialize_run_log(log):
    return {
        "scanner_kind": log.scanner_kind,
        "status": log.status,
        "findings_count": log.findings_count,
        "started_at": serialize_dt(log.started_at),
        "finished_at": serialize_dt(log.finished_at),
        "error": log.error,
    }


def enqueue_scan_job(scan_job) -> None:
    enqueue_task(
        "scan_job",
        {
            "scan_job_id": scan_job.id,
            "target_ids": scan_job.target_ids,
            "scanners": scan_job.scanner_selection,
        },
        async_job=scan_job.async_job,
    )


def enqueue_task(task_name: str, payload: dict, async_job=None) -> QueuedTask:
    return QueuedTask.objects.create(
        async_job=async_job,
        task_name=task_name,
        payload=payload,
        status=QueuedTask.QUEUED,
        available_at=timezone.now(),
    )


def request_cancel(async_job):
    terminal = {"COMPLETED", "FAILED", "CANCELLED"}
    if async_job.status in terminal:
        return False
    if async_job.kind == "recompute" and async_job.status == "RUNNING":
        return False
    if async_job.kind == "recompute" and async_job.status == "PENDING":
        async_job.status = "CANCELLED"
        async_job.finished_at = timezone.now()
    else:
        async_job.cancel_requested_at = timezone.now()
    async_job.save()
    return True
