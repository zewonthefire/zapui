# Docker Assets

This directory contains image definitions for the containerized ZapUI stack.

## Subdirectories

- `web/`: Django/Gunicorn image and startup entrypoint.
- `nginx/`: Nginx image used for reverse proxy and TLS termination.
- `ops/`: FastAPI Ops Agent image for controlled compose operations.
- `pdf/`: Placeholder wkhtmltopdf-based service image.

## Build usage

All images are built from the repository root through `docker-compose.yml`, for example:

```bash
docker compose build
```

## Operational note

Even though Dockerfiles live here, container wiring, environment variables, ports, mounts, and profiles are defined in the root `docker-compose.yml`.
