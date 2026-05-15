from django.db import models


class Asset(models.Model):
    snapshot = models.ForeignKey(
        "snapshots.CbomSnapshot",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    target = models.ForeignKey(
        "targets.Target",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )
    name = models.CharField(max_length=255)
    asset_class = models.CharField(max_length=32, default="crypto")
    asset_type = models.CharField(max_length=32, default="certificate")
    bom_ref = models.CharField(max_length=255, default="")
    algorithm = models.CharField(max_length=128, default="")
    algorithm_family = models.CharField(max_length=64, default="")
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "bom_ref"], name="uniq_asset_snapshot_bom_ref"),
        ]
        indexes = [
            models.Index(fields=["snapshot", "asset_type"], name="asset_snapshot_type_idx"),
            models.Index(fields=["snapshot", "target"], name="asset_snapshot_target_idx"),
            models.Index(fields=["bom_ref"], name="asset_bom_ref_idx"),
            models.Index(fields=["algorithm_family"], name="asset_algorithm_family_idx"),
        ]


class AssetContextOverride(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="context_override")
    sensitivity = models.CharField(max_length=16, null=True, blank=True)
    lifespan_years = models.IntegerField(null=True, blank=True)
    criticality = models.CharField(max_length=16, null=True, blank=True)
    exposure = models.CharField(max_length=32, null=True, blank=True)
    service_role = models.CharField(max_length=128, null=True, blank=True)
    override_keys = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.override_keys:
            self.override_keys = [
                field
                for field in ["sensitivity", "lifespan_years", "criticality", "exposure", "service_role"]
                if getattr(self, field) is not None
            ]
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["asset"], name="asset_context_asset_idx"),
        ]


class QualitativeAssessment(models.Model):
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name="qualitative_assessment")
    provider = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=64, default="")
    prompt_payload = models.JSONField(default=dict)
    summary = models.TextField()
    threat_scenarios = models.JSONField(default=list)
    migration_recommendation = models.TextField()
    dhs_criteria = models.JSONField(default=dict)
    confidence = models.FloatField(default=0.0)
    generated_at = models.DateTimeField(auto_now=True)


class AssetDependency(models.Model):
    snapshot = models.ForeignKey(
        "snapshots.CbomSnapshot",
        on_delete=models.CASCADE,
        related_name="asset_dependencies",
    )
    source_asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="dependency_edges",
    )
    target_asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="depended_by_edges",
    )
    relation_type = models.CharField(max_length=32, default="dependsOn")
    semantic = models.CharField(max_length=64, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_asset", "target_asset", "relation_type"],
                name="uniq_asset_dependency_edge",
            ),
        ]
        indexes = [
            models.Index(fields=["snapshot", "source_asset"], name="asset_dep_source_idx"),
            models.Index(fields=["snapshot", "target_asset"], name="asset_dep_target_idx"),
        ]
