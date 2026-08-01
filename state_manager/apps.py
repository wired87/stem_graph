from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class StateManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "state_manager"
    verbose_name = "Component state manager"

    def ready(self):
        from .drf import install_serializer_capture

        install_serializer_capture()
        autodiscover_modules("component_state")
