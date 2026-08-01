from django.urls import path

from product.components.stem_graph.views import StemGraphView
from product.views.check_run import DockerStatusAndDownloadView

urlpatterns = [
    path("run-local/", StemGraphView.as_view(), name="run-local"),
    path("status-run/<str:container_id>/", DockerStatusAndDownloadView.as_view(), name="status-run"),
]
