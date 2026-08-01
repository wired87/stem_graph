from django.urls import path

from .views import ComponentRegistryView, ComponentRequirementsView, ComponentStateView, SessionStateView

app_name = "state_manager"

urlpatterns = [
    path("session/", SessionStateView.as_view(), name="session"),
    path("registry/", ComponentRegistryView.as_view(), name="registry"),
    path("components/<str:component_key>/", ComponentStateView.as_view(), name="component"),
    path("components/<str:component_key>/requirements/", ComponentRequirementsView.as_view(), name="requirements"),
]
