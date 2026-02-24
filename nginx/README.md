# Nginx

Runtime ingress directory for ZapUI.

## Purpose
- terminate TLS
- proxy to Django web service
- enforce setup-stage routing behavior

## State and generated config
- `nginx/conf.d/default.conf` is generated at container startup.
- `nginx/state/setup_complete` controls HTTP redirect behavior.

### Behavior
- `setup_complete` present: HTTP redirects to HTTPS.
- `setup_complete` absent: HTTP + HTTPS both proxy to app, allowing setup wizard completion.

## Certificates
Expected files:
- `certs/fullchain.pem`
- `certs/privkey.pem`

If missing, container startup generates temporary self-signed certs to keep service bootable.
