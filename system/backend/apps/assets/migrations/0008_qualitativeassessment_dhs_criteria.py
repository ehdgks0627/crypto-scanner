from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0007_qualitativeassessment_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="qualitativeassessment",
            name="dhs_criteria",
            field=models.JSONField(default=dict),
        ),
    ]
