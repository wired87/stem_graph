from django.urls import path

from protein.components.protein_prediction.views import ProteinPredictionView
from protein.views import ProteinAumDownload, protein_workspace

app_name = "protein_predictor"

urlpatterns = [
    path("", protein_workspace, name="workspace"),
    path("predict/", ProteinPredictionView.as_view(), name="predict"),
    path("exports/<str:export_id>/aum.pdf", ProteinAumDownload.as_view(), name="aum_pdf"),
]
