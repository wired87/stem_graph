import os
from pathlib import Path

runtime_root = Path(os.getenv("STEMCNV_STATE_ROOT", "/tmp/stemgraph"))
runtime_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DUCK_DB_PATH", str(runtime_root / "firegraph.duckdb"))

from cnvmaster.settings import *  # noqa: E402,F403

ROOT_URLCONF = "cnvmaster.urls_stemcnv"
ALLOWED_HOSTS = ["*"]

# The StemCNV control plane deliberately loads only the apps it serves.  This
# keeps the web/worker image small and avoids importing the unrelated graph,
# protein and Firebase stacks into every API or queue-worker process.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "product",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "cnvmaster.middleware.RequestResponseMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
