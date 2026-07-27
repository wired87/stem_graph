from django.urls import path

from drug_master.views import PrecisionDrugWorkflow, drug_workspace


app_name = "drug_master"

urlpatterns = [
    path("", drug_workspace, name="workspace"),
    path("run/", PrecisionDrugWorkflow.as_view(), name="run"),
]
