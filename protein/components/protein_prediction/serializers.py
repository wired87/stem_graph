from rest_framework import serializers


class ProteinPredictionSerializer(serializers.Serializer):
    tissue = serializers.CharField(max_length=120, trim_whitespace=True)
    functional_annotation = serializers.CharField(max_length=500, trim_whitespace=True)
    protein_type = serializers.ChoiceField(
        choices=("", "Ion channel", "Enzyme", "Neuropeptide"),
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_tissue(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Enter a specific tissue name.")
        return value.strip()
