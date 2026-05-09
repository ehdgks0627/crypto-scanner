from django.db import models


class Discovery(models.Model):
    async_job = models.OneToOneField("jobs.AsyncJob", on_delete=models.CASCADE, related_name="discovery")
    scope_type = models.CharField(max_length=16, default="cidr")
    scope_value = models.CharField(max_length=253, default="")
    cidr = models.CharField(max_length=253)
    executor_type = models.CharField(max_length=16, default="central")
    discovery_agent = models.ForeignKey(
        "agents.Agent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_discoveries",
    )
    ports = models.JSONField(default=list)
    include_default_ports = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="PENDING")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(scope_type__in=["cidr", "ip", "domain"]), name="discovery_scope_type_valid"),
            models.CheckConstraint(condition=models.Q(executor_type__in=["central", "agent"]), name="discovery_executor_type_valid"),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="discovery_status_created_idx"),
            models.Index(fields=["scope_type", "-created_at"], name="discovery_scope_created_idx"),
            models.Index(fields=["executor_type", "-created_at"], name="discovery_executor_created_idx"),
            models.Index(fields=["discovery_agent", "-created_at"], name="discovery_agent_created_idx"),
        ]


class DiscoveredEndpoint(models.Model):
    discovery = models.ForeignKey(Discovery, on_delete=models.CASCADE, related_name="endpoints")
    host = models.CharField(max_length=253)
    port = models.PositiveIntegerField()
    transport = models.CharField(max_length=8, default="TCP")
    detected_protocol = models.CharField(max_length=32)
    suggested_protocol_hint = models.CharField(max_length=16)
    promoted = models.BooleanField(default=False)
    target = models.ForeignKey("targets.Target", null=True, blank=True, on_delete=models.SET_NULL)
    availability_metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["discovery", "promoted"], name="endpoint_discovery_prom_idx"),
            models.Index(fields=["host", "port", "transport"], name="endpoint_natural_idx"),
        ]
