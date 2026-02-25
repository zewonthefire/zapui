# Dashboard filters and routes

The Dashboard feature provides six pages:

- `/dashboard/overview/`
- `/dashboard/risk/`
- `/dashboard/findings/`
- `/dashboard/coverage/`
- `/dashboard/changes/`
- `/dashboard/operations/`

Each page includes a shared Context Bar. Filters are persisted in the URL query string so they can be copied between pages:

`?project_id=1&target_id=all&asset_id=all&node_id=all&profile_id=all&range=30d&scan_id=latest`

Supported filter keys:

- `project_id` (or `all`)
- `target_id` (or `all`)
- `asset_id` (or `all`)
- `node_id` (or `all`)
- `profile_id` (or `all`)
- `range` (`7d`, `30d`, `90d`, `custom`)
- `scan_id` (`latest` or an explicit scan job id)

Context option endpoint:

- `GET /api/context/options/`

Dashboard APIs:

- `GET /api/dashboard/overview/`
- `GET /api/dashboard/risk/`
- `GET /api/dashboard/findings/`
- `GET /api/dashboard/coverage/`
- `GET /api/dashboard/changes/`
- `GET /api/dashboard/operations/`

All APIs accept the same filter query string.
