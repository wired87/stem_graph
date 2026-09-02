from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("product", "0002_stemcnvartifact")]
    operations = [
        migrations.CreateModel(
            name="StemCNVInput",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=500)),
                ("size", models.PositiveBigIntegerField()),
                ("content", models.BinaryField()),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inputs", to="product.stemcnvrun")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="stemcnvinput",
            constraint=models.UniqueConstraint(fields=("run", "name"), name="unique_stemcnv_input"),
        ),
    ]
