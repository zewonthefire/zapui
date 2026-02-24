# Nginx Runtime Directory

This directory contains runtime state and startup logic used by the `nginx` service.

## Layout

- `scripts/entrypoint.sh`: Generates nginx config dynamically and creates temporary TLS material if needed.
- `conf.d/`: Host-mounted destination for generated nginx config (`default.conf`).
- `state/`: Setup lifecycle state (notably the `setup_complete` flag file).

## Behavior controlled by `state/setup_complete`

- If `state/setup_complete` exists:
  - HTTP (`:8080`) redirects to HTTPS.
  - HTTPS (`:8443`) proxies to Django.
- If it does not exist:
  - HTTP and HTTPS both proxy to Django to allow first-run setup over HTTP.

## Certificates

The nginx entrypoint expects:

- `/certs/fullchain.pem`
- `/certs/privkey.pem`

If either file is missing, a temporary self-signed certificate is generated so nginx can start.

## Static and media

The generated config exposes:

- `/static/` from `/static/`
- `/media/` from `/media/`

These are backed by compose volumes shared with the web container.
