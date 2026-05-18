from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.jobs.models import QueuedTask
from apps.performance import runner, services
from apps.performance.models import PerformanceEvaluationRun


def process_next_performance_run_task() -> dict | None:
    task = (
        QueuedTask.objects.filter(task_name="performance_run", status=QueuedTask.QUEUED, available_at__lte=timezone.now())
        .order_by("available_at", "id")
        .first()
    )
    if not task:
        return None
    return process_performance_run_task(task.id)


def process_performance_run_task(task_id: int) -> dict:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        if task.status == QueuedTask.CANCELLED:
            return {}
        if task.status != QueuedTask.QUEUED:
            raise ValueError(f"QueuedTask {task.id} is not queued")
        run = PerformanceEvaluationRun.objects.select_for_update().get(id=task.payload["run_id"])
        now = timezone.now()
        task.status = QueuedTask.RUNNING
        task.attempts += 1
        task.locked_at = now
        task.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        if run.status == PerformanceEvaluationRun.PENDING:
            run.status = PerformanceEvaluationRun.RUNNING
            run.started_at = run.started_at or now
            run.summary = {**(run.summary or {}), "runner": {"state": "queued"}}
            run.save(update_fields=["status", "started_at", "summary", "updated_at"])

    try:
        result = runner.run_performance_run(task.payload["run_id"])
    except Exception as exc:
        _fail_performance_run_task(task_id, exc)
        raise

    _complete_performance_run_task(task_id)
    return result


def _complete_performance_run_task(task_id: int) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        task.status = QueuedTask.COMPLETED
        task.last_error = None
        task.save(update_fields=["status", "last_error", "updated_at"])


def _fail_performance_run_task(task_id: int, exc: Exception) -> None:
    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().get(id=task_id)
        task.status = QueuedTask.FAILED
        task.last_error = str(exc)
        task.save(update_fields=["status", "last_error", "updated_at"])
        try:
            run = PerformanceEvaluationRun.objects.select_for_update().get(id=task.payload["run_id"])
        except PerformanceEvaluationRun.DoesNotExist:
            return
        services.update_run_status(
            run,
            PerformanceEvaluationRun.FAILED,
            {
                "runner": {
                    "state": "failed",
                    "error": str(exc)[:255],
                }
            },
        )
