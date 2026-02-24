# ZapControl Backend

Django backend for ZapUI.

## Apps
- `accounts`: custom email-based user model and login/logout
- `core`: setup wizard, dashboard, ops pages, global settings, middleware gating
- `targets`: projects/targets/profiles/jobs/findings/risk/evolution/reports

## Key backend capabilities
- setup wizard persistence and completion gating
- role-aware access controls (admin/security_engineer/readonly)
- ZAP node inventory and connectivity checks
- asynchronous scan orchestration via Celery
- findings normalization from raw ZAP alerts
- weighted risk snapshots (target/project/global)
- evolution diff computation between completed scans

## Important modules
- `core/views.py`: setup flow + ops + dashboard
- `core/middleware.py`: setup gating behavior
- `targets/tasks.py`: scan lifecycle orchestration
- `targets/risk.py`: normalization, risk, and scan comparison logic
- `targets/views.py`: UI flows for profiles/scans/evolution/reports

## Testing
Run from `backend/zapcontrol`:
```bash
DJANGO_DB_ENGINE=sqlite python manage.py test
```

## Related docs
- `README.md` (repo root)
- `docs/architecture.md`
- `docs/security.md`
- `docs/operations.md`
- `docs/api.md`
