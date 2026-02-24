# Web Image (`docker/web`)

Build context for the Django application runtime used by:

- `web` (Gunicorn)
- `worker` (Celery worker)
- `beat` (Celery beat)

## Files

- `Dockerfile`
- `entrypoint.sh`

## Image behavior

`Dockerfile`:

- Uses `python:3.12-slim`
- Installs app dependencies from `backend/zapcontrol/requirements.txt`
- Copies Django project into `/app`
- Sets `/entrypoint.sh` as container entrypoint

`entrypoint.sh`:

1. Ensures required directories exist (`/app/staticfiles`, `/app/mediafiles`, `/nginx-state`, `/certs`).
2. Runs Django migrations (`python manage.py migrate --noinput`).
3. Collects static files (`python manage.py collectstatic --noinput`).
4. Executes final runtime command (Gunicorn by default).

## Default command

```bash
gunicorn zapcontrol.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Celery services override the command in `docker-compose.yml` while reusing the same image.
