import uuid

from django.db import models


class Agent(models.Model):
    ROLE_HOST = "host"
    ROLE_DISCOVERY = "discovery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=253)
    agent_role = models.CharField(max_length=16, default=ROLE_HOST)
    agent_url = models.URLField(null=True, blank=True)
    capabilities = models.JSONField(default=list)
    os_distribution = models.CharField(max_length=128, null=True, blank=True)
    agent_token_hash = models.CharField(max_length=128)
    agent_runtime_token = models.CharField(max_length=128, null=True, blank=True)
    active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    token_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(agent_role__in=["host", "discovery"]),
                name="agent_role_valid",
            ),
            models.UniqueConstraint(fields=["hostname", "agent_role"], name="agent_hostname_role_uniq"),
        ]
        indexes = [
            models.Index(fields=["active", "last_seen"], name="agent_active_last_seen_idx"),
            models.Index(fields=["hostname"], name="agent_hostname_idx"),
            models.Index(fields=["agent_role", "active", "last_seen"], name="agent_role_active_seen_idx"),
        ]
