# ZapUI

ZapUI is a Dockerized control plane for OWASP ZAP scanning operations. It provides a guided setup wizard, multi-node scan orchestration, findings normalization, risk scoring, and evolution tracking so teams can move from raw scanner output to actionable, historical security operations.

## What this tool is
ZapUI is built for operators and security teams who need:
- central management of projects and targets/assets
- reusable scan profiles and queued scan jobs
- support for internal and external ZAP nodes
- persistent findings history instead of one-off raw alerts
- weighted risk scoring and trend/evolution analysis
- an install-and-operate model that works for fresh deployment and reconfiguration

## Core concepts

### Project
A logical application/security ownership boundary (example: `payments-api`).

### Target / Asset
A concrete URL/service/environment inside a project that can be scanned.

### Zap Node
Execution backend for scans.
- **internal_managed**: compose-managed ZAP daemon(s)
- **external**: remote ZAP endpoint added by operators

### Profile
Reusable scan template controlling scan type, spider behavior, node pinning, and max duration.

### Job
A single scan execution binding project + target + profile. Jobs move through pending/running/completed/failed.

### Findings
Normalized vulnerability records deduplicated by target + plugin + title, with finding instances and first/last seen lifecycle.

### Risk
Weighted severity scoring snapshots captured at:
- target scope
- project scope
- global scope

### Evolution
Comparison of consecutive completed scans for a target:
- new findings
- resolved findings
- risk delta

## Architecture at a glance
- `nginx`: ingress + TLS termination + setup redirect behavior
- `web` (Django/Gunicorn): UI/API, setup wizard, orchestration triggers
- `worker`/`beat` (Celery): async scan execution and scheduling
- `db` (PostgreSQL): primary persistence
- `redis`: broker/cache
- `zap`: internal ZAP daemon(s)
- `pdf`: report rendering helper
- `ops` (optional): privileged compose operations agent

See full docs:
- `docs/architecture.md`
- `docs/security.md`
- `docs/operations.md`
- `docs/api.md`

## Installation guide

### Option A: Interactive installer (recommended)
Run:
```bash
bash scripts/install.sh
```

Installer capabilities:
- safe to re-run (idempotent)
- prompts for install dir/repo/ports
- can pull latest code
- can toggle ops profile
- can rebuild images and re-apply compose
- updates `.env` values consistently

After install, open:
- `http://localhost:<PUBLIC_HTTP_PORT>/setup`

### Option B: Manual installation
1. Clone repository.
2. Create `.env` from `.env.example` and set required values.
3. Create runtime dirs:
   - `certs/`
   - `nginx/state/`
   - `nginx/conf.d/`
4. Build and start stack:
   ```bash
   docker compose build
   docker compose up -d
   ```
5. Complete `/setup` wizard.

## Setup wizard summary
Wizard is stateful and can resume. Steps:
1. Instance settings + DB mode (integrated/external PostgreSQL)
2. First admin user creation
3. TLS (generate self-signed or validate provided cert/key)
4. ZAP pool and optional external node connectivity test
5. Finalization and setup completion flag

## Production notes
- Replace all defaults and weak secrets.
- Use trusted TLS certificates.
- Restrict `DJANGO_ALLOWED_HOSTS`.
- Keep backups and verify restore process.
- Consider external managed PostgreSQL for production durability.
- Ensure observability/log retention for web/worker/nginx and scan workflows.

## Security notes

### Ops Agent warning
Ops Agent is **disabled by default**. If enabled, it can run compose operations and is security-sensitive.

### Docker socket warning
Ops Agent mounts `/var/run/docker.sock`, which is a high-privilege boundary. Treat access as host-level privileged access.

### Minimum controls
- strong `OPS_AGENT_TOKEN`
- least-privilege network exposure
- limit admin users
- rotate credentials and monitor audit logs

## Troubleshooting
- **Redirected to setup unexpectedly**: check setup completion state and `nginx/state/setup_complete`.
- **Cannot login**: ensure setup finished and admin account exists.
- **Node test fails**: verify node URL/API key/network reachability.
- **Scans not progressing**: inspect worker/redis/db connectivity and task logs.
- **HTTPS errors**: verify `certs/fullchain.pem` and `certs/privkey.pem`.
- **Ops controls unavailable**: confirm `ENABLE_OPS_AGENT=true`, `COMPOSE_PROFILES=ops`, and valid token.

## Backup/restore strategy
Back up these assets together:
- `db_data` volume (database)
- `media_data` volume (reports/files)
- `certs/` (TLS materials)
- `nginx/state/` (setup completion and runtime state)

Recommended approach:
- scheduled volume snapshots + DB dumps
- off-host encrypted copies
- retention policy and restore drills

Restore outline:
1. Stop stack.
2. Restore DB/media/certs/nginx state.
3. Start stack.
4. Validate health, auth, and recent reporting data.

## Upgrade strategy
1. Take full backup.
2. Pull latest code (or re-run installer with pull enabled).
3. Rebuild images and apply compose updates.
4. Verify migrations/boot logs.
5. Smoke-test login, node connectivity, scan lifecycle, reports, evolution pages.
6. Roll back by restoring backup if regression appears.

## Docs and onboarding map
- `README.md` (this file): complete deploy/operator overview
- `docs/architecture.md`: service architecture and concept model
- `docs/security.md`: hardening and privileged boundaries
- `docs/operations.md`: day-2 runbooks, backup/restore, upgrades
- `docs/api.md`: endpoint reference
- `scripts/README.md`: installer usage details
- `backend/zapcontrol/README.md`: backend internals
- `nginx/README.md`: ingress and setup-flag behavior
