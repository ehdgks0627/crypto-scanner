import uuid

from django.db import models


class Agent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=253, unique=True)
    agent_url = models.URLField(null=True, blank=True)
    capabilities = models.JSONField(default=list)
    os_distribution = models.CharField(max_length=128, null=True, blank=True)
    agent_token_hash = models.CharField(max_length=128)
    active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    token_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["active", "last_seen"], name="agent_active_last_seen_idx"),
            models.Index(fields=["hostname"], name="agent_hostname_idx"),
        ]
