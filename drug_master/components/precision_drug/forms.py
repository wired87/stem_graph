import json
from django import forms


class PrecisionDrugForm(forms.Form):
    accessions = forms.CharField(widget=forms.Textarea, max_length=1000)
    sex = forms.ChoiceField(
        required=False,
        choices=(("", "Not supplied"), ("female", "Female"),
                 ("male", "Male"), ("intersex", "Intersex")),
    )
    vep_annotations = forms.CharField(required=False, widget=forms.Textarea)

    def clean_vep_annotations(self):
        raw = self.cleaned_data.get("vep_annotations") or "[]"
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Enter a valid JSON list.") from exc
        if not isinstance(value, list):
            raise forms.ValidationError("VEP annotations must be a JSON list.")
        return value
