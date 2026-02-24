# Nginx Image (`docker/nginx`)

Image responsible for ZapUI ingress and TLS termination.

---

## Build details

- base image: `nginx:1.27-alpine`,
- installs `openssl` to support temporary cert generation,
- copies runtime entrypoint from `nginx/scripts/entrypoint.sh`,
- starts nginx via `/entrypoint.sh`.

---

## Runtime behavior sources

Image behavior depends on mounted runtime assets:

- `nginx/scripts/entrypoint.sh`,
- `nginx/state/setup_complete`,
- certificate files mounted under `/certs`,
- generated config output under `/etc/nginx/conf.d`.

See `nginx/README.md` for the full operational model.

---

## Operational notes

- keep cert files mounted and valid for production,
- verify generated config on startup if routing behavior is unexpected,
- inspect logs with `docker compose logs nginx`.
