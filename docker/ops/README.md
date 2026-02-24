# Ops Agent (`docker/ops`)

FastAPI service providing controlled compose-level operations for ZapUI.

---

## Purpose

Ops Agent allows admin workflows (restart/rebuild/redeploy/scale/logs) from the application control surface when explicitly enabled.

It is disabled by default and should be treated as high-trust infrastructure.

---

## Files

- `Dockerfile`
- `requirements.txt`
- `main.py`

---

## Endpoint model

### Public

- `GET /health`

### Token-protected (`X-OPS-TOKEN`)

- `GET /compose/services`
- `GET /compose/logs/{service}`
- `POST /compose/restart/{service}`
- `POST /compose/rebuild`
- `POST /compose/redeploy`
- `POST /compose/scale`
- `GET /compose/env-summary`

---

## Guardrails

- actions are allowed only when `ENABLE_OPS_AGENT=true`,
- token required via `OPS_AGENT_TOKEN`,
- service names validated against compose service inventory,
- intended for internal compose network usage only.

---

## Critical security warning

When enabled, this service mounts Docker socket and project directory.
That is privileged access and can affect the full host runtime in many setups.

Use only in trusted environments with strict admin access control and credential hygiene.
