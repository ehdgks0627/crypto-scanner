from django.db import models


class CbomSnapshot(models.Model):
    scan_job = models.ForeignKey("jobs.ScanJob", null=True, blank=True, on_delete=models.SET_NULL)
    serial_number = models.CharField(max_length=128, default="")
    summary = models.JSONField(default=dict)
    validation_errors = models.JSONField(default=list)
    cbom_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"], name="snapshot_created_desc_idx"),
            models.Index(fields=["scan_job"], name="snapshot_scan_job_idx"),
        ]
