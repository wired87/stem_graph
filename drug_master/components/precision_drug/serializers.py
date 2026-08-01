import json
from rest_framework import serializers


class AccessionInputField(serializers.Field):
    default_error_messages = {"invalid": "Use a list or whitespace/comma-separated text."}

    def to_internal_value(self, value):
        if isinstance(value, (list, tuple)):
            raw_values = value
        elif isinstance(value, str):
            raw_values = value.replace(",", " ").split()
        else:
            self.fail("invalid")
        accessions = list(dict.fromkeys(str(item).strip().upper() for item in raw_values if str(item).strip()))
        if not accessions:
            raise serializers.ValidationError("At least one UniProt accession is required.")
        if len(accessions) > 50:
            raise serializers.ValidationError("A maximum of 50 accessions is supported.")
        return accessions

    def to_representation(self, value):
        return value


class FlexibleJSONListField(serializers.JSONField):
    def to_internal_value(self, value):
        if value in (None, ""):
            return []
        return super().to_internal_value(value)


class PrecisionDrugSerializer(serializers.Serializer):
    accessions = AccessionInputField()
    sex = serializers.ChoiceField(choices=("female", "male", "intersex"), required=False,
                                  allow_blank=True, allow_null=True)
    vep_annotations = FlexibleJSONListField(required=False, default=list)

    def validate_vep_annotations(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Enter a valid JSON list.") from exc
        if not isinstance(value, list):
            raise serializers.ValidationError("VEP annotations must be a JSON list.")
        return value
