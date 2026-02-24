# ZapUI Skeleton: Dockerized ZAP Control Center Bootstrap

This repository now provides an **initial skeleton** for a future ZAP Control Center UI focused on:

- Projects
- Targets
- Scans
- Findings
- Risk scoring
- Evolution/trending

> This is intentionally only the baseline infrastructure + minimal backend wiring. Wizard, domain models, and scan workflows are not implemented yet.

## What this skeleton includes

- Single `docker-compose.yml` at repo root
- Nginx reverse proxy with HTTP + HTTPS
- Temporary TLS generation on boot if certs are missing
- Minimal Django app (`backend/zapcontrol`) behind Gunicorn
- Django authentication foundation with a custom user model and role support
- Celery worker + beat placeholders
- PostgreSQL + Redis
- Internal-only OWASP ZAP daemon (`zaproxy/zap-stable`) on the compose network
- Placeholder PDF container (`wkhtmltopdf` image-based)
- FastAPI Ops Agent (profile-gated, disabled by default)
- Interactive installer script (`scripts/install.sh`)
- Operator Makefile targets for lifecycle tasks

## Architecture overview

```text
Host ports
  PUBLIC_HTTP_PORT (default 8090)  ---> nginx:8080
  PUBLIC_HTTPS_PORT (default 443)  ---> nginx:8443

nginx -> web (gunicorn Django)
web   -> db (PostgreSQL)
web   -> redis
web   -> zap:8090 (internal only)
worker/beat -> redis + db
```

### Services

- `nginx`: TLS termination and reverse proxy for Django
- `web`: Django + Gunicorn (includes migrations + collectstatic on startup)
- `worker`: Celery worker placeholder runtime
- `beat`: Celery beat placeholder runtime
- `redis`: broker/cache backend
- `db`: PostgreSQL database
- `zap`: OWASP ZAP daemon mode; exposed only inside Docker network
- `pdf`: placeholder microservice (wkhtmltopdf installed)
- `ops`: FastAPI operations agent (disabled unless profile `ops` is enabled)

## Nginx behavior

Nginx uses file flag `./nginx/state/setup_complete` (mounted at `/nginx-state/setup_complete`).

- If the flag **exists**: HTTP redirects to HTTPS.
- If the flag is **missing**: HTTP proxies to Django so setup can run on first boot.

HTTPS server is always defined and uses:

- `/certs/fullchain.pem`
- `/certs/privkey.pem`

If missing, the nginx entrypoint generates a temporary self-signed certificate so startup does not fail.

## Authentication and role model

The Django foundation now uses a custom user model (`accounts.User`) with email-based login and three built-in roles:

- `admin`
- `security_engineer`
- `readonly`

Authentication routes:

- `GET/POST /login`
- `GET /logout`
- `GET /dashboard` (requires login)

Admin remains available at `/admin/`.

## Basic navigation and endpoints

UI shell includes a Bootstrap top navigation with links for dashboard, setup placeholder, and API version.

Application/API endpoints currently available:

- `GET /health` -> `{"status":"ok"}`
- `GET /setup` -> setup placeholder response (wizard not implemented yet)
- `GET /dashboard` -> authenticated dashboard shell
- `GET /api/version` -> `{"name":"zapcontrol","version":"..."}`


## Operations subsystem (baseline)

The repo now includes an Operations subsystem with:

- `ops` FastAPI service for container monitoring and lifecycle tasks.
- Django admin-only operations pages:
  - `/ops/overview` (service status + connectivity checks)
  - `/ops/logs/<service>` (tail logs)
  - `/ops/actions` (restart/rebuild/redeploy with password re-confirmation)

### Security model

- **Ops Agent is disabled by default.**
- Controlled by `ENABLE_OPS_AGENT=false` (default).
- Enable by setting:
  - `ENABLE_OPS_AGENT=true`
  - `OPS_AGENT_TOKEN=<strong secret>`
  - `COMPOSE_PROFILES=ops`
- Agent listens only on the internal compose network (`ops:8091`) and has no host port mapping.
- Agent requires `X-OPS-TOKEN` header for privileged compose endpoints.
- Agent enforces a strict service allowlist derived from this compose project (`COMPOSE_PROJECT_NAME`).

### Docker socket warning

When `ops` runs, it mounts `/var/run/docker.sock` and project directory into the agent container so it can execute:

- `docker compose build <services>`
- `docker compose up -d --no-deps <services>`

Treat the ops container as highly privileged. Use a strong `OPS_AGENT_TOKEN`, restrict who can access internal services, and keep ops disabled unless needed.

### Common workflows

Restart `web` from UI:

1. Open `/ops/actions` as an admin user.
2. Select restart + service `web`.
3. Re-enter your password to confirm.

Rebuild and redeploy `web` from UI:

1. Open `/ops/actions`.
2. Use `rebuild` with services `web`.
3. Use `redeploy` with services `web`.
4. Confirm each action with password re-auth.

Read-only mode when disabled:

- `/ops/overview` still shows DB/Redis/ZAP connectivity tests.
- Action pages display clear enablement instructions.

## Installation

### Option A: Quick install (interactive)

```bash
bash scripts/install.sh
```

### Option B: Manual install

```bash
git clone https://github.com/zewonthefire/zapui ~/zapui
cd ~/zapui
cp .env.example .env
mkdir -p certs nginx/state nginx/conf.d
docker compose up -d --build
```

## Configuration

All environment values live in `.env`.

Key values:

- `PUBLIC_HTTP_PORT` (default `8090`)
- `PUBLIC_HTTPS_PORT` (default `443`)
- `ENABLE_OPS_AGENT` (`no` default)
- `COMPOSE_PROFILES` (set to `ops` to enable `ops` service)
- `DJANGO_*` settings
- `POSTGRES_*` settings
- `CELERY_*` settings

## Makefile shortcuts

- `make up` - start containers
- `make down` - stop containers
- `make logs` - stream logs
- `make migrate` - run Django migrations in `web`
- `make collectstatic` - collect static assets in `web`
- `make rebuild` - build + start

## Django admin bootstrap

Create an admin user from the web container:

```bash
docker compose exec web python manage.py createsuperuser
```

After creating the account, sign in at `/login` or `/admin/`.

## Migrations workflow in Docker

Use these as the default migration workflow:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

For a fresh bootstrap run, `web` startup already executes migrations automatically, but explicit commands above are recommended when iterating on models.

## Security notes

- CSRF middleware is enabled.
- Session and CSRF cookies are configured to be secure in HTTPS environments.
- Session expiry defaults to 8 hours (`SESSION_COOKIE_AGE`) and can be tuned via env vars.
- First-run HTTP is intentionally available for setup flow bootstrapping.
- Add `nginx/state/setup_complete` once setup is done to force HTTP->HTTPS redirect.
- Replace temporary certs with trusted certificates in `./certs`.
- ZAP API is internal-only by default (no host port binding).
- Ops Agent is disabled by default because agent capabilities can expand operational blast radius if compromised.

## Troubleshooting

### Services won’t boot

```bash
docker compose ps
docker compose logs --tail=200 nginx web db redis zap
```

### Health check test

```bash
curl -i http://localhost:8090/health
```

### Verify ZAP internal connectivity from web container

```bash
docker compose exec web python - <<'PY'
import requests
print(requests.get('http://zap:8090').status_code)
PY
```

### HTTPS certificate warnings

A browser warning is expected with the temporary self-signed certificate. Replace cert files in `./certs` with your own cert/key pair.

---

## Current scope / non-goals

This skeleton does **not** implement:

- full setup wizard logic
- project/target/scan domain models
- scan orchestration
- finding normalization and risk scoring
- reporting pipeline

Those are intentionally deferred for later iterations.
