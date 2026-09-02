from django.urls import path

from product.components.stem_graph.views import StemGraphView
from product.views.check_run import DockerStatusAndDownloadView, LatestStemCNVRunView

urlpatterns = [
    path("run-local/", StemGraphView.as_view(), name="run-local"),
    path("status-run/<str:container_id>/", DockerStatusAndDownloadView.as_view(), name="status-run"),
    path("latest-run/", LatestStemCNVRunView.as_view(), name="latest-run"),
]
