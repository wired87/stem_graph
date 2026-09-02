from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("product", "0001_stemcnvrun")]
    operations = [
        migrations.CreateModel(
            name="StemCNVArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(max_length=500)),
                ("size", models.PositiveBigIntegerField()),
                ("content", models.BinaryField()),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="product.stemcnvrun")),
            ],
            options={"ordering": ["path"]},
        ),
        migrations.AddConstraint(
            model_name="stemcnvartifact",
            constraint=models.UniqueConstraint(fields=("run", "path"), name="unique_stemcnv_artifact"),
        ),
    ]
