from django.db import models


class StemCNVRun(models.Model):
    run_id = models.CharField(max_length=80, primary_key=True)
    container_id = models.CharField(max_length=128)
    status = models.CharField(max_length=24, default="created")
    input_source = models.CharField(max_length=32)
    output_name = models.CharField(max_length=100)
    cores = models.PositiveSmallIntegerField(default=4)
    events = models.JSONField(default=list)
    logs = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class StemCNVArtifact(models.Model):
    run = models.ForeignKey(StemCNVRun, related_name="artifacts", on_delete=models.CASCADE)
    path = models.CharField(max_length=500)
    size = models.PositiveBigIntegerField()
    content = models.BinaryField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "path"], name="unique_stemcnv_artifact")]
        ordering = ["path"]


class StemCNVInput(models.Model):
    run = models.ForeignKey(StemCNVRun, related_name="inputs", on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    size = models.PositiveBigIntegerField()
    content = models.BinaryField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "name"], name="unique_stemcnv_input")]
        ordering = ["name"]

# Create your models here.
