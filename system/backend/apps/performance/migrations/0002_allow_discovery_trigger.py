from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("performance", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="performanceevaluationrun",
            name="perf_run_trigger_valid",
        ),
        migrations.AddConstraint(
            model_name="performanceevaluationrun",
            constraint=models.CheckConstraint(
                condition=models.Q(("trigger__in", ["manual", "post_migration", "scheduled", "canary", "discovery"])),
                name="perf_run_trigger_valid",
            ),
        ),
    ]
