# Docker Assets

This directory contains image definitions used by the ZapUI compose stack.

---

## Subdirectories

- `web/` - Django/Gunicorn runtime image used by web/worker/beat services.
- `nginx/` - nginx ingress image and startup behavior.
- `pdf/` - internal HTML-to-PDF rendering service.
- `ops/` - optional privileged operations agent image.

---

## Build model

Dockerfiles live here, but service wiring is defined in root `docker-compose.yml`:

- networks,
- volume mounts,
- environment variables,
- profiles,
- startup commands,
- port exposure.

Build from repository root:

```bash
docker compose build
```

---

## Operational guidance

- treat `ops` image as privileged when profile enabled,
- keep base images and dependencies updated,
- rebuild images during upgrades to apply security patches,
- inspect per-image READMEs for service-specific behavior.
