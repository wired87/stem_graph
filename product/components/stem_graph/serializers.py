from pathlib import Path
from rest_framework import serializers

from product.stemcnv_docker import validate_upload_bundle

ALLOWED_SUFFIXES = {".idat", ".bpm", ".egt", ".csv", ".tsv", ".txt", ".yaml", ".yml", ".xlsx", ".gz"}
MAX_FILE_SIZE = 250 * 1024 * 1024


class StemGraphSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), required=False, allow_empty=True, default=list)
    output_name = serializers.RegexField(
        r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$", required=False, default="stemcnv-results.zip"
    )
    annotate_variants = serializers.BooleanField(required=False, default=False)
    functional_annotation = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    function_similarity_threshold = serializers.FloatField(required=False, default=0.75, min_value=0, max_value=1)
    cores = serializers.IntegerField(required=False, default=3, min_value=1, max_value=64)

    def validate_output_name(self, value):
        return value if value.lower().endswith(".zip") else f"{value}.zip"

    def validate_files(self, files):
        errors = []
        for upload in files:
            suffix = Path(upload.name).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                errors.append(f"{upload.name}: unsupported file type {suffix or '(none)'}")
            if upload.size > MAX_FILE_SIZE:
                errors.append(f"{upload.name}: exceeds the 250 MiB limit")
            content_type = (getattr(upload, "content_type", "") or "").lower()
            if content_type and not content_type.startswith(("text/", "application/")):
                errors.append(f"{upload.name}: unsupported MIME type {content_type}")
        if errors:
            raise serializers.ValidationError(errors)
        if files:
            try:
                validate_upload_bundle(files)
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return files
