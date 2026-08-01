from django.urls import path

from drug_master.components.precision_drug.views import PrecisionDrugComponentView
from drug_master.views import DrugArtifactDownload, drug_workspace

app_name = "drug_master"

urlpatterns = [
    path("", drug_workspace, name="workspace"),
    path("run/", PrecisionDrugComponentView.as_view(), name="run"),
    path("exports/<str:export_id>/<str:filename>", DrugArtifactDownload.as_view(), name="artifact"),
]
