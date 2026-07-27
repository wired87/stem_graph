from django.urls import path
from protein.views import ProteinPredictor, protein_workspace

app_name = "protein_predictor"

urlpatterns = [
    path('', protein_workspace, name='workspace'),
    path('predict/', ProteinPredictor.as_view(), name='predict'),
]

