# Scripts

Operational scripts for deploying and maintaining ZapUI.

---

## `install.sh`

Interactive installer/upgrader designed for safe day-0 and day-2 operations.

### Core capabilities

- idempotent and safe to re-run,
- clone repository or reuse existing checkout,
- optional `git pull --ff-only` for updates,
- configurable public HTTP/HTTPS ports,
- optional enable/disable of Ops Agent profile,
- optional image build/rebuild with upstream refresh,
- compose reconciliation using `docker compose up -d --remove-orphans`,
- explicit status output and endpoint summary.

### Why this matters

The script is designed to reduce operational drift and provide a consistent update path without requiring manual `.env` surgery each time.

### Usage

```bash
bash scripts/install.sh
```

### Typical scenarios

- first installation on a new host,
- changing public ingress ports,
- enabling/disabling ops profile,
- pulling latest code and rebuilding images,
- applying config updates after maintenance windows.

### Safety notes

- Ops Agent enablement is explicitly prompted with a warning because it is privileged.
- Script checks for `git` and `docker` availability before continuing.
- Existing `.env` values are upserted rather than blindly overwritten.
