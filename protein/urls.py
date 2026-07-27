from django.urls import path
from protein.view import ProteinPredictor

app_name = "protein_predictor"

urlpatterns = [
    path('predict/', ProteinPredictor.as_view()),
]

