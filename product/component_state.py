from state_manager.registry import register_component

from product.components.stem_graph.forms import StemGraphForm
from product.components.stem_graph.serializers import StemGraphSerializer
from product.components.stem_graph.views import StemGraphView


register_component(
    "product.stem_graph",
    form_class=StemGraphForm,
    serializer_class=StemGraphSerializer,
    view_class=StemGraphView,
    provides=("stem.graph", "stem.table"),
)
