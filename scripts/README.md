# Scripts Directory

This folder contains helper scripts for bootstrapping and operating ZapUI.

## Files

- `install.sh`: Interactive installer that clones or updates the repo, writes key `.env` values, builds images, and starts the compose stack.

## `install.sh` workflow

1. Prompts for install directory, repository URL, HTTP/HTTPS ports, and whether to enable the Ops Agent.
2. Clones the repository if missing, or runs a fast-forward pull if it already exists.
3. Creates required runtime folders (`certs`, `nginx/state`, `nginx/conf.d`).
4. Creates `.env` from `.env.example` when missing.
5. Upserts runtime values:
   - `PUBLIC_HTTP_PORT`
   - `PUBLIC_HTTPS_PORT`
   - `ENABLE_OPS_AGENT`
   - `COMPOSE_PROFILES`
6. Runs:
   - `docker compose build`
   - `docker compose up -d`

## Usage

```bash
bash scripts/install.sh
```

## Notes

- Enabling Ops Agent sets `COMPOSE_PROFILES=ops`.
- Installer does not generate long-lived trusted certs; temporary/self-signed cert behavior is handled by nginx container startup.
