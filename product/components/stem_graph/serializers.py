from pathlib import Path
from rest_framework import serializers

ALLOWED_SUFFIXES = {".idat", ".bpm", ".egt", ".csv", ".tsv", ".txt", ".yaml", ".yml"}
MAX_FILE_SIZE = 250 * 1024 * 1024


class StemGraphSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)
    annotate_variants = serializers.BooleanField(required=False, default=False)
    functional_annotation = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    function_similarity_threshold = serializers.FloatField(required=False, default=0.75, min_value=0, max_value=1)

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
        return files
