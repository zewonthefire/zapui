# Ops Agent (`docker/ops`)


## Documentation Changelog
- Date: 2026-02-24
- Added: Code-verified operational details, commands, and cross-links.
- Clarified: Security posture, runtime behavior, and service boundaries.
- Deprecated: None in this pass.
- Appendix: N/A (no original content removed).

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
- `POST /compose/env/upsert-zap-api-key`

---

## Guardrails

- actions are allowed only when `ENABLE_OPS_AGENT=true`,
- token required via `OPS_AGENT_TOKEN`,
- service names validated against compose service inventory,
- `POST /compose/env/upsert-zap-api-key` patches `PROJECT_DIR/docker-compose.yml` (expected default layout),
- intended for internal compose network usage only.

---

## Critical security warning

When enabled, this service mounts Docker socket and project directory.
That is privileged access and can affect the full host runtime in many setups.

Use only in trusted environments with strict admin access control and credential hygiene.

---

## 2026 Documentation Enrichment

### Code-verified quick commands
```bash
# Validate compose configuration
docker compose config

# Show running services
docker compose ps

# Tail main application logs
docker compose logs -f --tail=200 web worker beat nginx
```

### Related docs
- Root entrypoint: `README.md`
- Canonical runtime facts: `docs/CODE_REALITY.md`
- Validation checklist: `docs/DOCS_QA_CHECKLIST.md`

No original content removed in this file.
