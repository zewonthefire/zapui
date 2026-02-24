# PDF Service Placeholder (`docker/pdf`)

This image is currently a placeholder microservice used to reserve a future PDF/reporting integration point.

## Files

- `Dockerfile`

## Behavior

- Base image: `alpine:3.20`
- Installs `wkhtmltopdf`
- Starts a no-op long-running command to keep the container alive

Current command:

```bash
sh -c "echo 'PDF service placeholder running'; tail -f /dev/null"
```

No HTTP API is exposed yet.
