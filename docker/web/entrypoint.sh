#!/usr/bin/env sh
set -eu

mkdir -p /app/staticfiles /app/mediafiles /nginx-state /certs
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
