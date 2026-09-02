from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="StemCNVRun",
            fields=[
                ("run_id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("container_id", models.CharField(max_length=128)),
                ("status", models.CharField(default="created", max_length=24)),
                ("input_source", models.CharField(max_length=32)),
                ("output_name", models.CharField(max_length=100)),
                ("cores", models.PositiveSmallIntegerField(default=4)),
                ("events", models.JSONField(default=list)),
                ("logs", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        )
    ]
