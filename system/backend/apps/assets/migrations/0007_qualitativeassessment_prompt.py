from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0006_asset_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="qualitativeassessment",
            name="prompt_version",
            field=models.CharField(default="", max_length=64),
        ),
        migrations.AddField(
            model_name="qualitativeassessment",
            name="prompt_payload",
            field=models.JSONField(default=dict),
        ),
    ]
