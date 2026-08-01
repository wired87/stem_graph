from django import forms


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        values = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleFileField, self).clean(value, initial) for value in values]


class StemGraphForm(forms.Form):
    files = MultipleFileField()
    annotate_variants = forms.BooleanField(required=False)
    functional_annotation = forms.CharField(required=False, widget=forms.Textarea)
    function_similarity_threshold = forms.FloatField(initial=0.75, min_value=0, max_value=1)
