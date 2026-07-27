#!/usr/bin/env python
# DRF API entrypoint: migrate DB then expose Django on 0.0.0.0 (used by root Dockerfile)
import os
import sys
from pathlib import Path

# Project root and accounts package on import path (same as manage.py / wsgi)
_BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / 'user'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cnvmaster.settings')


def main() -> None:
    from django.core.management import execute_from_command_line

    # apply migrations before serving (MVP container boot)
    execute_from_command_line(['main', 'migrate', '--noinput'])
    # bind all interfaces so Docker port mapping works
    host = os.getenv('DJANGO_HOST', '0.0.0.0')
    port = os.getenv('DJANGO_PORT', '8000')
    execute_from_command_line(['main', 'runserver', f'{host}:{port}'])


if __name__ == '__main__':
    main()
