from django.urls import path

from product.views.check_run import DockerStatusAndDownloadView
from product.views.run_local import RunLocalSampleView

urlpatterns = [
    path('run-local/', RunLocalSampleView.as_view(), name='run-local'),
    #path('run-sample/', RunSampleView.as_view(), name='product-run-sample'),
    path('status-run/<str:container_id>/', DockerStatusAndDownloadView.as_view(), name='status-run'),]
