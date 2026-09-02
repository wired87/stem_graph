#!/bin/sh
set -eu

i=0
until python manage.py migrate --noinput; do
  i=$((i + 1))
  if [ "$i" -ge "${DATABASE_WAIT_ATTEMPTS:-30}" ]; then
    echo "Database migration failed after $i attempts" >&2
    exit 1
  fi
  sleep 2
done
exec daphne -b 0.0.0.0 -p "${PORT:-8080}" cnvmaster.asgi:application
