from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0004_queuedtask"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="queuedtask",
            name="queued_task_status_valid",
        ),
        migrations.AddConstraint(
            model_name="queuedtask",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]),
                name="queued_task_status_valid",
            ),
        ),
    ]
