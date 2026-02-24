# Nginx Runtime

This directory stores runtime assets used by the `nginx` service in ZapUI.

---

## Purpose

Nginx provides:

- HTTP/HTTPS ingress,
- TLS termination,
- request proxying to Django,
- setup-phase routing behavior,
- static/media path serving.

---

## Directory layout

- `scripts/entrypoint.sh`
  - generates runtime `default.conf`,
  - ensures cert material exists (temporary fallback generation when missing),
  - controls setup-complete routing mode.
- `conf.d/`
  - generated nginx configuration output.
- `state/`
  - runtime state flags, including setup completion marker.

---

## Setup completion behavior

`state/setup_complete` controls HTTP behavior:

- present: HTTP requests redirect to HTTPS,
- absent: HTTP and HTTPS both proxy to app (to allow first-run setup path).

This behavior aligns ingress policy with application setup state.

---

## Certificate behavior

Expected certificate files:

- `certs/fullchain.pem`
- `certs/privkey.pem`

If missing, nginx startup creates temporary self-signed certs to keep service bootable.
Production environments must replace these with trusted certificates.

---

## Static and media exposure

Nginx serves:

- `/static/` from shared static volume,
- `/media/` from shared media volume.

These locations are mounted from application-generated assets.

---

## Troubleshooting

- if HTTPS fails, verify cert files and permissions,
- if setup redirects are wrong, verify `state/setup_complete`,
- inspect logs with `docker compose logs nginx`.
