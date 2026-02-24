# Operations

## Day-0 deployment
1. Run `bash scripts/install.sh`.
2. Open `/setup` and finish all wizard steps.
3. Validate `/health`, login, and a sample scan.

## Idempotent installer behavior
`scripts/install.sh` is safe to re-run and supports:
- reusing existing checkout
- optional fast-forward pull
- changing public ports and re-applying compose
- toggling ops profile and re-applying
- rebuilding images with latest upstream layers

## Daily workflows
- View service and connectivity state at `/ops/overview` (admin).
- Manage nodes at `/zapnodes`.
- Launch scans at `/scans`.
- Review reports and evolution pages.

## Backups
Critical persistence locations:
- `db_data` (PostgreSQL)
- `media_data` (reports/uploads)
- `certs/` (TLS cert/key)
- `nginx/state/` (setup state and runtime flags)

Recommended strategy:
- scheduled DB dump + volume snapshot
- checksum verification + retention policy
- off-host encrypted copies
- routine restore drills

## Restore
1. Stop stack: `docker compose down`.
2. Restore DB/media/certs/nginx_state artifacts.
3. Start stack: `docker compose up -d`.
4. Validate `/health`, login, and recent scans/reports.

## Upgrades
1. Create backup before change.
2. Pull latest code.
3. Re-run installer and choose build/rebuild.
4. Run migrations (handled by web startup entrypoint).
5. Smoke test setup flag, login, scan lifecycle, report download.
6. Roll back by restoring previous artifacts if needed.

## Troubleshooting quick list
- Setup redirect loops: verify `SetupState` and `nginx/state/setup_complete` consistency.
- Node unhealthy: verify ZAP API reachability and API key.
- Jobs stuck pending/running: check worker/redis logs and broker connectivity.
- HTTPS issues: verify cert files and permissions.
- Ops actions unavailable: confirm `ENABLE_OPS_AGENT=true`, profile `ops`, and token alignment.
