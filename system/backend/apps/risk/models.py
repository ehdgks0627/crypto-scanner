from django.db import models


class RiskWeights(models.Model):
    wA = models.FloatField(default=1.0)
    wD = models.FloatField(default=1.0)
    wE = models.FloatField(default=1.0)
    wL = models.FloatField(default=1.0)
    wC = models.FloatField(default=1.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(wA__gte=0.5, wA__lte=2.0), name="risk_weight_wa_range"),
            models.CheckConstraint(condition=models.Q(wD__gte=0.5, wD__lte=2.0), name="risk_weight_wd_range"),
            models.CheckConstraint(condition=models.Q(wE__gte=0.5, wE__lte=2.0), name="risk_weight_we_range"),
            models.CheckConstraint(condition=models.Q(wL__gte=0.5, wL__lte=2.0), name="risk_weight_wl_range"),
            models.CheckConstraint(condition=models.Q(wC__gte=0.5, wC__lte=2.0), name="risk_weight_wc_range"),
        ]


class RiskScore(models.Model):
    snapshot = models.ForeignKey("snapshots.CbomSnapshot", on_delete=models.CASCADE, related_name="risk_scores")
    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE, related_name="risk_scores")
    score = models.FloatField()
    tier = models.CharField(max_length=16)
    factors = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(score__gte=0, score__lte=100), name="risk_score_range"),
            models.CheckConstraint(condition=models.Q(tier__in=["CRITICAL", "HIGH", "MEDIUM", "LOW"]), name="risk_tier_valid"),
        ]
        indexes = [
            models.Index(fields=["snapshot", "tier", "-score"], name="risk_snapshot_tier_score_idx"),
            models.Index(fields=["asset"], name="risk_asset_idx"),
        ]
