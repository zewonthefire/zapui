# Ops Agent (`docker/ops`)

FastAPI service that provides guarded operational actions for this compose project.

## Files

- `Dockerfile`
- `requirements.txt`
- `main.py`

## Endpoints

Unauthenticated:

- `GET /health`

Token-protected (via `X-OPS-TOKEN`) and gated by `ENABLE_OPS_AGENT=true`:

- `GET /compose/services`
- `GET /compose/logs/{service}`
- `POST /compose/restart/{service}`
- `POST /compose/rebuild`
- `POST /compose/redeploy`
- `POST /compose/scale`
- `GET /compose/env-summary`

## Security model

- Agent actions are disabled unless `ENABLE_OPS_AGENT` is truthy.
- Token auth requires `OPS_AGENT_TOKEN`.
- Service arguments are validated against compose-discovered services (`docker compose ps --all --format json`).
- Intended for internal-only access on the compose network (`ops:8091`).

## Important warning

When enabled, this service uses mounted docker socket and project directory, so treat it as privileged infrastructure.
