# Backend

This directory contains the ZapUI backend source code.

## Structure

- `zapcontrol/`
  - Django project and app modules,
  - templates, migrations, task logic,
  - domain models for scans/findings/risk/evolution/reporting.

## Responsibilities

The backend handles:

- setup wizard and setup gating,
- authentication and role-based access,
- scan orchestration with ZAP nodes,
- findings normalization and risk scoring,
- evolution diff computation,
- report generation and downloads,
- operations-facing control and audit surfaces.

## Primary backend documentation

- detailed guide: `backend/zapcontrol/README.md`
- architecture: `docs/architecture.md`
- operations runbook: `docs/operations.md`
- endpoint map: `docs/api.md`
- security model: `docs/security.md`

## Basic validation

From `backend/zapcontrol`:

```bash
DJANGO_DB_ENGINE=sqlite python manage.py test
```
