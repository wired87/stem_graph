"""
ASGI config for cnvmaster project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file_master, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import sys
from pathlib import Path

# expose user/accounts as top-level `accounts` package (auth + billing imports)
_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR / "user"))

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cnvmaster.settings')

application = get_asgi_application()
