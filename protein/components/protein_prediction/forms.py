from django import forms


class ProteinPredictionForm(forms.Form):
    tissue = forms.CharField(max_length=120, initial="Thalamus")
    functional_annotation = forms.CharField(
        max_length=500,
        initial="synaptic transmission",
    )
    protein_type = forms.ChoiceField(
        required=False,
        choices=(
            ("", "No class restriction"),
            ("Ion channel", "Ion channel"),
            ("Enzyme", "Enzyme"),
            ("Neuropeptide", "Neuropeptide"),
        ),
    )
