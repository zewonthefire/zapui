# ZapUI Skeleton: Dockerized ZAP Control Center Bootstrap

This repository now provides an **initial skeleton** for a future ZAP Control Center UI focused on:

- Projects
- Targets
- Scans
- Findings
- Risk scoring
- Evolution/trending

> This repo now includes a first-run setup wizard with persistence, TLS handling, and initial ZAP configuration.

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

UI shell includes Bootstrap navigation and a full first-run setup wizard at `/setup`.

Application/API endpoints currently available:

- `GET /health` -> `{"status":"ok"}`
- `GET/POST /setup` -> multi-step first-run setup wizard
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

- `/ops/overview` still shows DB/Redis/ZAP connectivity tests and node inventory.
- Action pages display clear enablement instructions.


## Setup wizard walkthrough

The wizard is available on `http://<host>:<PUBLIC_HTTP_PORT>/setup` while setup is incomplete.

Steps:

1. **Instance settings + database**: instance name, external base URL, display HTTP port reference, and database mode (integrated by default or external PostgreSQL with connectivity test).
2. **First admin user**: creates the initial admin account with strong password validation.
3. **TLS**: either generate a self-signed cert with SANs (`localhost`, `127.0.0.1`, external hostname) or validate an existing cert/key pair in `./certs`.
4. **ZAP configuration**: choose desired internal pool size (default `1`), optionally register one external ZAP node, and run connectivity checks.
5. **Finalize**: run health checks (including DB mode-specific connectivity), write `nginx/state/setup_complete`, and display the final HTTPS URL.

After finalization, nginx redirects all HTTP traffic to HTTPS on restart because the setup flag exists.

- If external DB is selected, the wizard stores runtime DB env overrides and attempts to disable the internal `db` service (via Ops Agent when enabled).
- If Ops Agent is disabled, wizard provides the manual stop command for internal DB after external DB cutover.
- Wizard progress is persisted server-side, and `/setup?step=<n>` resume links are shown to tolerate HTTP↔HTTPS transitions during setup.

## ZAP pool size and scaling

- Default pool size is `1` internal `zap` container.
- `/ops/overview` can scale up or down using one compose stack only (no extra compose files).
- Shrinking the pool disables stale internal ZapNode records instead of hard-deleting them.
- If Ops Agent is disabled, use manual command `make scale-zap N=<count>`.

## ZapNode management

- Open `/zapnodes` as an admin user to manage node inventory.
- **External nodes**:
  - Add with `name`, `base_url`, and optional `api_key`.
  - Use **Test** (per-node) or **Test all nodes** to call `/JSON/core/view/version/` and store status, latency, and timestamp.
  - Remove external nodes directly from the UI.
- **Internal managed nodes**:
  - Created automatically when internal pool scaling is applied.
  - Node records keep `docker_container_name` and internal service URL (`http://<container_name>:8090`).
  - When pool is reduced, missing containers are retained as disabled records for history/audit.

## Internal pool scaling (single compose file)

- Use `/ops/overview` (admin only) to set **Desired pool size** and apply.
- With Ops Agent enabled, ZapUI runs `docker compose up -d --scale zap=N` through the agent API.
- After scaling, ZapUI discovers running `zap` service containers and syncs `internal_managed` ZapNode records.
- You can also run **Test all nodes** from `/ops/overview` or `/zapnodes`.


## Scan orchestration (Celery + ZAP API)

ZapUI now includes baseline scan orchestration with persisted profiles/jobs/results and support for multiple ZapNodes.

### Scan types and flow

- `baseline_like`: run spider (if enabled) then active scan, poll completion, fetch raw alerts.
- `full_active`: same orchestration as baseline for now (spider + active scan), with profile-level controls for timeout/options.
- `api_scan`: placeholder type; jobs are created but marked failed with `API scan is not implemented yet.`

Execution is handled by Celery task `start_scan_job`:

1. Resolve node (profile pinning or auto-select).
2. Start spider and poll `/JSON/spider/view/status/` until complete (when enabled).
3. Start active scan and poll `/JSON/ascan/view/status/` until complete.
4. Fetch raw alerts via `/JSON/core/view/alerts/`.
5. Persist `RawZapResult` and mark job complete.

On transient node/network failures, task retries with backoff. If node failure persists or happens mid-scan after retries, the job is marked failed and **is not auto-migrated** to another node.

### Node selection strategy

Node selection for a `ScanJob` follows:

1. If `ScanProfile.zap_node` is set, use that node only when it is enabled + healthy.
2. Otherwise, choose an enabled+healthy node with the lowest count of currently running jobs.
3. If no healthy node exists, fall back to the first enabled node.
4. If no enabled node exists, fail job start.

### UI paths

- `/profiles`: create/update/delete scan profiles.
- `/scans`: list scan jobs + submit new scan job.
- `/scans/<id>`: job detail, ZAP IDs, and latest raw alerts payload.

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
- `make scale-zap N=<count>` - scale internal ZAP replicas manually when ops agent is disabled

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
- If you choose to expose ZAP for local debugging, bind to loopback only, for example `127.0.0.1:8090:8090` (never `0.0.0.0`).
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

- project/target/scan domain models
- scan orchestration
- finding normalization and risk scoring
- reporting pipeline

Those are intentionally deferred for later iterations.
