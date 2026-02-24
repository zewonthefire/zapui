# API and UI endpoints

## Public/health endpoints
- `GET /health` -> service heartbeat JSON.
- `GET /api/version` -> application version payload.

## Auth endpoints
- `GET|POST /login`
- `GET /logout`

## Setup endpoints
- `GET|POST /setup` multi-step wizard with persisted progress.

## Core UI endpoints
- `GET /dashboard`
- `GET /ops/overview`
- `GET /ops/actions`
- `GET /ops/logs/<service>`
- `GET|POST /zapnodes`

## Scanning/risk endpoints
- `GET|POST /profiles`
- `GET|POST /scans`
- `GET /scans/<id>`
- `GET /scans/<id>/report/<html|json|pdf>`
- `GET /reports`
- `GET /projects/<id>`
- `GET /targets/<id>`
- `GET /targets/<id>/evolution`
- `GET /targets/<id>/evolution/<comparison_id>`

## Internal integration APIs used by backend
### OWASP ZAP JSON API
- `/JSON/core/view/version/`
- `/JSON/spider/action/scan/`
- `/JSON/spider/view/status/`
- `/JSON/ascan/action/scan/`
- `/JSON/ascan/view/status/`
- `/JSON/core/view/alerts/`

### Ops Agent API (optional)
- `/compose/services`
- `/compose/scale`
- `/compose/logs/{service}`
- `/compose/restart`
- `/compose/build`
- `/compose/up`

All privileged ops calls require `X-OPS-TOKEN` and admin-side password re-confirmation in UI flows.
