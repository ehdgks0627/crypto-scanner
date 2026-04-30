from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def default_context():
    return {
        "sensitivity": None,
        "lifespan_years": None,
        "criticality": None,
        "exposure": None,
        "service_role": None,
    }


class Target(models.Model):
    host = models.CharField(max_length=253)
    display_name = models.CharField(max_length=120, null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    port = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(65535)])
    protocol_hint = models.CharField(max_length=16)
    sni = models.CharField(max_length=253, null=True, blank=True)
    transport = models.CharField(max_length=8, default="TCP")
    agent_enabled = models.BooleanField(default=False)
    agent_url = models.URLField(null=True, blank=True)
    context = models.JSONField(default=default_context)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["host", "port", "transport"], name="uniq_target_host_port_transport"),
            models.CheckConstraint(condition=models.Q(port__gte=1, port__lte=65535), name="target_port_range_valid"),
            models.CheckConstraint(condition=models.Q(transport__in=["TCP", "UDP"]), name="target_transport_valid"),
        ]
        indexes = [
            models.Index(fields=["host"], name="target_host_idx"),
            models.Index(fields=["protocol_hint"], name="target_protocol_hint_idx"),
            models.Index(fields=["agent_enabled"], name="target_agent_enabled_idx"),
            models.Index(fields=["-created_at"], name="target_created_desc_idx"),
        ]
