from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("discoveries", "0004_discovery_executor"),
    ]

    operations = [
        migrations.AddField(
            model_name="discoveredendpoint",
            name="availability_metrics",
            field=models.JSONField(default=dict),
        ),
    ]
