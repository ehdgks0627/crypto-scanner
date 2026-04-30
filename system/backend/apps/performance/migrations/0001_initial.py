from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("assets", "0005_asset_bom_ref_and_dependencies"),
        ("snapshots", "0004_remove_cbomsnapshot_cbom_json"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerformanceEvaluationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger", models.CharField(default="manual", max_length=32)),
                ("profile", models.CharField(default="smoke", max_length=32)),
                ("status", models.CharField(default="PENDING", max_length=20)),
                ("thresholds", models.JSONField(default=dict)),
                ("environment", models.JSONField(default=dict)),
                ("summary", models.JSONField(default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "baseline_snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="candidate_performance_runs",
                        to="snapshots.cbomsnapshot",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_runs", to="snapshots.cbomsnapshot"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AssetPerformanceResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(max_length=16)),
                ("compatibility_status", models.CharField(default="PASS", max_length=16)),
                ("negotiated_algorithm", models.CharField(blank=True, max_length=128)),
                ("metrics", models.JSONField(default=dict)),
                ("deltas", models.JSONField(default=dict)),
                ("signals", models.JSONField(default=list)),
                ("recommendation", models.CharField(default="manual_review", max_length=64)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                ("measured_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_history", to="assets.asset")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="performance.performanceevaluationrun")),
            ],
        ),
        migrations.AddConstraint(
            model_name="performanceevaluationrun",
            constraint=models.CheckConstraint(condition=models.Q(("trigger__in", ["manual", "post_migration", "scheduled", "canary"])), name="perf_run_trigger_valid"),
        ),
        migrations.AddConstraint(
            model_name="performanceevaluationrun",
            constraint=models.CheckConstraint(condition=models.Q(("profile__in", ["smoke", "baseline", "canary", "stress"])), name="perf_run_profile_valid"),
        ),
        migrations.AddConstraint(
            model_name="performanceevaluationrun",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["PENDING", "RUNNING", "COMPLETED", "FAILED"])), name="perf_run_status_valid"),
        ),
        migrations.AddIndex(
            model_name="performanceevaluationrun",
            index=models.Index(fields=["snapshot", "-created_at"], name="perf_run_snapshot_created_idx"),
        ),
        migrations.AddIndex(
            model_name="performanceevaluationrun",
            index=models.Index(fields=["status", "-created_at"], name="perf_run_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="performanceevaluationrun",
            index=models.Index(fields=["baseline_snapshot"], name="perf_run_baseline_idx"),
        ),
        migrations.AddConstraint(
            model_name="assetperformanceresult",
            constraint=models.UniqueConstraint(fields=("run", "asset"), name="uniq_perf_result_run_asset"),
        ),
        migrations.AddConstraint(
            model_name="assetperformanceresult",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["PASS", "WARN", "FAIL", "ERROR"])), name="perf_result_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="assetperformanceresult",
            constraint=models.CheckConstraint(condition=models.Q(("compatibility_status__in", ["PASS", "WARN", "FAIL", "ERROR"])), name="perf_result_compat_status_valid"),
        ),
        migrations.AddIndex(
            model_name="assetperformanceresult",
            index=models.Index(fields=["run", "status"], name="perf_result_run_status_idx"),
        ),
        migrations.AddIndex(
            model_name="assetperformanceresult",
            index=models.Index(fields=["asset", "-measured_at"], name="perf_result_asset_measured_idx"),
        ),
    ]
