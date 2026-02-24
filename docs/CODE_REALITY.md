# CODE_REALITY (Canonical Runtime Facts)

## Documentation Changelog
- Date: 2026-02-24
- Added: Code-extracted truth source for service topology, env vars, endpoints, and behavior.
- Clarified: What is actually implemented versus planned behavior.
- Deprecated: None.
- Appendix: N/A (new file).

## Compose services (`docker-compose.yml`)
- `nginx`: exposes `${PUBLIC_HTTP_PORT:-8090}:8080` and `${PUBLIC_HTTPS_PORT:-443}:8443`.
- `web`: Django/Gunicorn app, depends on `db`, `redis`, `zap`, `pdf`.
- `worker`: Celery worker (`celery -A zapcontrol worker -l info`).
- `beat`: Celery beat scheduler.
- `redis`: broker/cache (`redis:7-alpine`).
- `db`: PostgreSQL (`postgres:16-alpine`).
- `zap`: `zaproxy/zap-stable` daemon on port `8090` with API key disabled by default.
- `pdf`: Flask + wkhtmltopdf internal renderer (`docker/pdf`).
- `ops`: FastAPI Ops Agent (profile `ops`; Docker socket mounted).

## Environment variables (observed in `.env.example` and settings)
- Core web: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`.
- Database: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`.
- Queueing: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- Ops: `ENABLE_OPS_AGENT`, `OPS_AGENT_TOKEN`, `OPS_AGENT_URL`, `COMPOSE_PROFILES`.
- Ingress: `PUBLIC_HTTP_PORT`, `PUBLIC_HTTPS_PORT`.
- PDF: `PDF_SERVICE_URL`.

## Django routes (`backend/zapcontrol/zapcontrol/urls.py`)
- Core: `/health`, `/setup`, `/dashboard`, `/api/version`.
- Ops UI: `/ops/overview`, `/ops/logs/<service>`, `/ops/actions`.
- Auth: `/login`, `/logout`.
- Scanning: `/profiles`, `/scans`, `/scans/<id>`, report downloads.
- Assets/evolution: `/projects/<id>`, `/targets/<id>`, `/targets/<id>/evolution`.

## Scan orchestration truth (`targets/tasks.py`)
- Node selection prefers profile-pinned healthy node; otherwise lowest running-job healthy node.
- `api_scan` profile type currently hard-fails with “not implemented yet”.
- Spider phase optional by profile.
- Active scan phase always run for implemented profile types.
- Alerts are normalized to findings, risk snapshots are produced, comparison diff is generated, and reports are generated.

## Security-relevant behavior
- Setup middleware blocks most routes until `SetupState(pk=1).is_complete` is true.
- Secure cookies default to enabled when `DJANGO_DEBUG=0`.
- Ops Agent remains opt-in and token-protected, but Docker socket mount is a high-trust boundary.
