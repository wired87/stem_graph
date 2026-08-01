from state_manager.registry import register_component

from protein.components.protein_prediction.forms import ProteinPredictionForm
from protein.components.protein_prediction.serializers import ProteinPredictionSerializer
from protein.components.protein_prediction.views import ProteinPredictionView


register_component(
    "protein.prediction",
    form_class=ProteinPredictionForm,
    serializer_class=ProteinPredictionSerializer,
    view_class=ProteinPredictionView,
    provides=("protein.candidates", "protein.context"),
)
