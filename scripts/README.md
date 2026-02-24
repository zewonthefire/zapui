# Scripts

## install.sh
Interactive, idempotent installer/upgrader for ZapUI.

### Features
- safe re-run behavior
- clone or reuse existing checkout
- optional `git pull --ff-only`
- port updates (`PUBLIC_HTTP_PORT`, `PUBLIC_HTTPS_PORT`) with compose re-apply
- ops profile toggle (`ENABLE_OPS_AGENT`, `COMPOSE_PROFILES`)
- optional image build/rebuild (`docker compose build --pull`)
- clear status output and final access URLs

### Usage
```bash
bash scripts/install.sh
```

### Typical scenarios
- Fresh install on new host
- Reconfigure public ports
- Enable/disable ops profile
- Pull latest source and rebuild services

### Notes
The script updates `.env` keys in-place and then runs `docker compose up -d --remove-orphans` so changes are applied consistently.
