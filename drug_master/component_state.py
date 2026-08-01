from state_manager.registry import register_component

from drug_master.components.precision_drug.forms import PrecisionDrugForm
from drug_master.components.precision_drug.serializers import PrecisionDrugSerializer
from drug_master.components.precision_drug.views import PrecisionDrugComponentView


register_component(
    "drug.precision",
    form_class=PrecisionDrugForm,
    serializer_class=PrecisionDrugSerializer,
    view_class=PrecisionDrugComponentView,
    provides=("drug.graph", "drug.artifacts"),
    requires=("protein.candidates",),
)
