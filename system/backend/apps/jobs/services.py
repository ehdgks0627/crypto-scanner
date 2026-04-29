from datetime import UTC

from django.utils import timezone

from apps.jobs.models import AsyncJob, QueuedTask


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
    scan_job = log.async_job.scan_job
    target_label = f"{log.target.host}:{log.target.port}"
    return {
        "id": log.id,
        "scan_job_id": scan_job.id,
        "target_id": log.target_id,
        "target_label": target_label,
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
    if async_job.status == AsyncJob.CANCELLED:
        now = timezone.now()
        update_fields = []
        if async_job.cancel_requested_at is None:
            async_job.cancel_requested_at = now
            update_fields.append("cancel_requested_at")
        if async_job.finished_at is None:
            async_job.finished_at = now
            update_fields.append("finished_at")
        if update_fields:
            async_job.save(update_fields=[*update_fields, "updated_at"])
        _cancel_queued_tasks(async_job)
        _sync_cancelled_resource(async_job, async_job.finished_at or now)
        return True
    terminal = {AsyncJob.COMPLETED, AsyncJob.FAILED}
    if async_job.status in terminal:
        return False
    if async_job.kind == "recompute" and async_job.status == AsyncJob.RUNNING:
        return False

    now = timezone.now()
    async_job.status = AsyncJob.CANCELLED
    async_job.cancel_requested_at = async_job.cancel_requested_at or now
    async_job.finished_at = async_job.finished_at or now
    async_job.save(update_fields=["status", "cancel_requested_at", "finished_at", "updated_at"])
    _cancel_queued_tasks(async_job)
    _sync_cancelled_resource(async_job, now)
    return True


def _cancel_queued_tasks(async_job):
    async_job.queued_tasks.filter(status__in=[QueuedTask.QUEUED, QueuedTask.RUNNING]).update(
        status=QueuedTask.CANCELLED,
        last_error="cancel_requested",
        updated_at=timezone.now(),
    )


def _sync_cancelled_resource(async_job, finished_at):
    if async_job.kind != "discovery":
        return

    from apps.discoveries.models import Discovery

    try:
        discovery = async_job.discovery
    except Discovery.DoesNotExist:
        return

    update_fields = []
    if discovery.status != AsyncJob.CANCELLED:
        discovery.status = AsyncJob.CANCELLED
        update_fields.append("status")
    if discovery.finished_at is None:
        discovery.finished_at = finished_at
        update_fields.append("finished_at")
    if not discovery.error:
        discovery.error = "cancel_requested"
        update_fields.append("error")
    if update_fields:
        discovery.save(update_fields=[*update_fields, "updated_at"])
