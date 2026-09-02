from django.urls import include, path

from cnvmaster import views
from cnvmaster.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("", views.stemcnv_home, name="home"),
    path("workspace/cnv/", views.cnv_workspace, name="cnv-workspace"),
    path("api/product/", include("product.urls")),
]
