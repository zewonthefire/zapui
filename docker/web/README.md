# Web Image (`docker/web`)

Container image for the Django application runtime reused by:

- `web` (Gunicorn),
- `worker` (Celery worker),
- `beat` (Celery scheduler).

---

## Contents

- `Dockerfile`
- `entrypoint.sh`

---

## Dockerfile behavior

- base image: `python:3.12-slim`,
- installs Python dependencies from `backend/zapcontrol/requirements.txt`,
- copies backend application into `/app`,
- installs `/entrypoint.sh` as container entrypoint.

---

## Entrypoint behavior

At startup, entrypoint:

1. creates required runtime directories,
2. runs `python manage.py migrate --noinput`,
3. runs `python manage.py collectstatic --noinput`,
4. executes final container command.

Default command for web service:

```bash
gunicorn zapcontrol.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Celery services override command in compose while reusing the same image and dependencies.

---

## Notes

- migration-on-start behavior is convenient for small deployments,
- for larger environments, evaluate dedicated migration control workflows.
