# Installation Guide

## Documentation Changelog
- Date: 2026-02-24
- Added: End-to-end install flows (interactive + manual).
- Clarified: Port/profile behavior and post-install checks.
- Deprecated: None.
- Appendix: N/A (new file).

## Option A: Interactive installer
```bash
bash scripts/install.sh
```

Installer behavior:
1. Clones or reuses repo directory.
2. Creates `.env` from `.env.example` when missing.
3. Prompts for `PUBLIC_HTTP_PORT` and `PUBLIC_HTTPS_PORT`.
4. Prompts to enable Ops Agent (`ENABLE_OPS_AGENT` + `COMPOSE_PROFILES=ops`).
5. Optionally builds images, then applies stack with `docker compose up -d --remove-orphans`.

## Option B: Manual
```bash
git clone https://github.com/zewonthefire/zapui.git
cd zapui
cp .env.example .env
mkdir -p certs nginx/state nginx/conf.d
docker compose up -d --build
```

## Verification
```bash
docker compose ps
curl -f http://localhost:${PUBLIC_HTTP_PORT:-8090}/health
```

## First-run setup URL
- `http://localhost:${PUBLIC_HTTP_PORT:-8090}/setup`
