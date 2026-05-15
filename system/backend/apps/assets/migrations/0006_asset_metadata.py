from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0005_asset_bom_ref_and_dependencies"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="metadata",
            field=models.JSONField(default=dict),
        ),
    ]
