from django.db import models


class AsyncJob(models.Model):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    kind = models.CharField(max_length=20)
    resource_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default=PENDING)
    request_payload = models.JSONField(default=dict)
    progress = models.JSONField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["scan_job", "discovery", "recompute"]),
                name="async_job_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]),
                name="async_job_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "status"], name="async_job_kind_status_idx"),
            models.Index(fields=["status", "-created_at"], name="async_job_status_created_idx"),
        ]


class ScanJob(models.Model):
    async_job = models.OneToOneField(AsyncJob, on_delete=models.CASCADE, related_name="scan_job")
    target_ids = models.JSONField(default=list)
    scanner_selection = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ScanRunLog(models.Model):
    async_job = models.ForeignKey(AsyncJob, on_delete=models.CASCADE, related_name="run_logs")
    target = models.ForeignKey("targets.Target", null=True, blank=True, on_delete=models.SET_NULL)
    scanner_kind = models.CharField(max_length=64)
    status = models.CharField(max_length=20)
    findings_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["async_job", "status"], name="scan_run_job_status_idx"),
            models.Index(fields=["scanner_kind", "status"], name="scan_run_scanner_status_idx"),
        ]


class QueuedTask(models.Model):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    async_job = models.ForeignKey(AsyncJob, null=True, blank=True, on_delete=models.CASCADE, related_name="queued_tasks")
    task_name = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default=QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]),
                name="queued_task_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "available_at"], name="queue_status_available_idx"),
            models.Index(fields=["task_name", "status"], name="queue_task_status_idx"),
        ]
