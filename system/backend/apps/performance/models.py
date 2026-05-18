from django.db import models


RUN_TRIGGERS = ["manual", "post_migration", "scheduled", "canary", "discovery"]
RUN_PROFILES = ["smoke", "baseline", "canary", "stress"]
RUN_STATUSES = ["PENDING", "RUNNING", "COMPLETED", "FAILED"]
RESULT_STATUSES = ["PASS", "WARN", "FAIL", "ERROR"]


class PerformanceEvaluationRun(models.Model):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    TRIGGERS = RUN_TRIGGERS
    PROFILES = RUN_PROFILES
    STATUSES = RUN_STATUSES

    snapshot = models.ForeignKey("snapshots.CbomSnapshot", on_delete=models.CASCADE, related_name="performance_runs")
    baseline_snapshot = models.ForeignKey(
        "snapshots.CbomSnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="candidate_performance_runs",
    )
    trigger = models.CharField(max_length=32, default="manual")
    profile = models.CharField(max_length=32, default="smoke")
    status = models.CharField(max_length=20, default="PENDING")
    thresholds = models.JSONField(default=dict)
    environment = models.JSONField(default=dict)
    summary = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(trigger__in=RUN_TRIGGERS), name="perf_run_trigger_valid"),
            models.CheckConstraint(condition=models.Q(profile__in=RUN_PROFILES), name="perf_run_profile_valid"),
            models.CheckConstraint(condition=models.Q(status__in=RUN_STATUSES), name="perf_run_status_valid"),
        ]
        indexes = [
            models.Index(fields=["snapshot", "-created_at"], name="perf_run_snapshot_created_idx"),
            models.Index(fields=["status", "-created_at"], name="perf_run_status_created_idx"),
            models.Index(fields=["baseline_snapshot"], name="perf_run_baseline_idx"),
        ]


class AssetPerformanceResult(models.Model):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    ERROR = "ERROR"
    STATUSES = RESULT_STATUSES

    run = models.ForeignKey(PerformanceEvaluationRun, on_delete=models.CASCADE, related_name="results")
    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE, related_name="performance_history")
    status = models.CharField(max_length=16)
    compatibility_status = models.CharField(max_length=16, default="PASS")
    negotiated_algorithm = models.CharField(max_length=128, blank=True)
    metrics = models.JSONField(default=dict)
    deltas = models.JSONField(default=dict)
    signals = models.JSONField(default=list)
    recommendation = models.CharField(max_length=64, default="manual_review")
    error_message = models.CharField(max_length=255, blank=True)
    measured_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "asset"], name="uniq_perf_result_run_asset"),
            models.CheckConstraint(condition=models.Q(status__in=RESULT_STATUSES), name="perf_result_status_valid"),
            models.CheckConstraint(condition=models.Q(compatibility_status__in=RESULT_STATUSES), name="perf_result_compat_status_valid"),
        ]
        indexes = [
            models.Index(fields=["run", "status"], name="perf_result_run_status_idx"),
            models.Index(fields=["asset", "-measured_at"], name="perf_result_asset_measured_idx"),
        ]
