from cnvmaster.settings import *  # noqa: F403

ROOT_URLCONF = "product.test_stemcnv_docker_route"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
