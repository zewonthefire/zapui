# Configuration Reference

## Documentation Changelog
- Date: 2026-02-24
- Added: Practical env-var reference tied to code paths.
- Clarified: Defaults, behavior, and profile gating.
- Deprecated: None.
- Appendix: N/A (new file).

## Core `.env` keys
```dotenv
PUBLIC_HTTP_PORT=8090
PUBLIC_HTTPS_PORT=443
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=*
DJANGO_CSRF_TRUSTED_ORIGINS=
POSTGRES_DB=zapui
POSTGRES_USER=zapui
POSTGRES_PASSWORD=zapui
ENABLE_OPS_AGENT=false
OPS_AGENT_TOKEN=change-me-ops-token
OPS_AGENT_URL=http://ops:8091
COMPOSE_PROFILES=
PDF_SERVICE_URL=http://pdf:8092
```

## Runtime configuration commands
```bash
# Show fully rendered compose config
docker compose config

# Check specific env var resolved in web container
docker compose exec web env | rg '^PDF_SERVICE_URL='
```

## Notes
- Set strong `DJANGO_SECRET_KEY` in production.
- Narrow `DJANGO_ALLOWED_HOSTS`.
- Use `COMPOSE_PROFILES=ops` only when Ops Agent is explicitly required.
