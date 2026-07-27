# Infrastructure section URL routes
from django.urls import path

from infrastructure.views.machine import MachineOffView, MachineOnView

# Infrastructure API endpoint patterns
urlpatterns = [
    # Machine on route
    path('machine/on/', MachineOnView.as_view(), name='infrastructure-machine-on'),
    # Machine off route
    path('machine/off/', MachineOffView.as_view(), name='infrastructure-machine-off'),
]
