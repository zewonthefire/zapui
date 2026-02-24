# ZapControl Backend Guide

This README documents the Django backend located in `backend/zapcontrol`.
It covers architecture, data model, scan orchestration, findings normalization, risk scoring, and local operations.

---

## 1) What this backend does

ZapControl is the application API/UI backend for:

- authentication and role-based access
- setup wizard and instance configuration
- ZAP node inventory and health checks
- scan profile/job orchestration via Celery
- raw alert persistence
- normalized findings lifecycle
- weighted risk snapshots for target/project/global scopes
- asset evolution diffs between consecutive successful scans

Primary app modules:

- `accounts`: custom user model and login/logout flow
- `core`: dashboard, setup wizard, ops pages, global settings
- `targets`: projects, targets, profiles, scan jobs, findings/risk

---

## 2) Runtime architecture

### Django process

- Entrypoint: `manage.py`
- Settings package: `zapcontrol.settings`
- URL root: `zapcontrol.urls`

### Async execution

- Celery worker executes scan orchestration task(s)
- Redis used as broker/cache
- PostgreSQL used for persistence

### External integrations

- OWASP ZAP API (`/JSON/...`) through configured `ZapNode`
- Optional Ops Agent for compose operations

---

## 3) Data model overview

The security/scanning domain lives in `targets.models`.

### Core scanning entities

- `Project` -> logical application grouping
- `Target` -> scan endpoint/environment within a project
- `ScanProfile` -> scan strategy/template
- `ScanJob` -> single execution record
- `RawZapResult` -> unmodified alerts payload captured per job

### Normalized findings entities

- `Finding`
  - dedup key: `(target, zap_plugin_id, title)`
  - tracks `first_seen`, `last_seen`, `instances_count`
- `FindingInstance`
  - concrete occurrence tied to `scan_job`
  - uniqueness includes `url`, `parameter`, `evidence`

### Risk entities

- `RiskSnapshot`
  - `scan_job` required
  - `project` nullable
  - `target` nullable
  - `risk_score` numeric
  - `counts_by_severity` JSON

Scope semantics:

- Target risk snapshot: `target != null`, `project == null`
- Project risk snapshot: `project != null`, `target == null`
- Global risk snapshot: both null

---

## 4) Scan lifecycle and orchestration

Task entrypoint: `targets.tasks.start_scan_job`.

High-level flow:

1. Resolve execution node (profile-pinned or auto-selected healthy node)
2. Optionally run spider and poll status
3. Run active scan and poll status
4. Fetch alerts from ZAP API
5. Persist `RawZapResult`
6. Normalize alerts into `Finding` + `FindingInstance`
7. Compute and persist `RiskSnapshot` for target/project/global
8. Compute and persist `ScanComparison` against the previous successful scan for the target
9. Mark job completed (or failed/retried on errors)

Notes:

- transient network/timeouts are retried with Celery autoretry
- API scan type currently exists as a placeholder and is marked failed

---

## 5) Findings normalization

Normalization module: `targets/risk.py`.

Rules implemented:

- Deduplicate by `(target, zap_plugin_id, title)`
- Map alert severity aliases into canonical severities: `High`, `Medium`, `Low`, `Info`
- Create/update `Finding`:
  - initialize `first_seen` and `last_seen` for new records
  - update `last_seen` on recurrence
- Create `FindingInstance` per unique URL/parameter/evidence tuple
- Recompute and store `instances_count` on each affected finding

This turns volatile raw alerts into stable, trackable findings over time.

---

## 6) Risk scoring model

Default weights:

- High = 10
- Medium = 5
- Low = 2
- Info = 1

Configurable via `core.Setting`:

- key: `risk_weights`
- value: JSON object, e.g.

```json
{
  "High": 12,
  "Medium": 6,
  "Low": 2,
  "Info": 1
}
```

Score formula used for each scope:

`risk_score = (High_count * W_high) + (Medium_count * W_medium) + (Low_count * W_low) + (Info_count * W_info)`

Generated per completed scan:

- target score
- project score
- global score

---



## 7) Evolution tracking and diff computation

Evolution tracking captures what changed between the newest completed scan and the prior completed scan for the same target.

Model: `ScanComparison`

- `target` -> target being compared
- `from_scan_job` -> older successful scan
- `to_scan_job` -> newer successful scan
- `new_finding_ids` -> finding IDs present in `to` but not in `from`
- `resolved_finding_ids` -> finding IDs present in `from` but not in `to`
- `risk_delta` -> `to_target_risk_score - from_target_risk_score`
- `created_at` -> comparison creation timestamp

Computation details:

1. On scan completion, normalization and risk snapshots run first.
2. The task selects the immediately previous successful scan for the same target.
3. Finding sets are built from `FindingInstance` rows per scan (distinct `finding_id`).
4. Deltas are computed as set differences:
   - `new = current - previous`
   - `resolved = previous - current`
5. Risk delta is derived from target-level `RiskSnapshot` values for those two scans.
6. A single `ScanComparison` row is created/updated for that scan pair.

This provides a stable historical chain of scan-to-scan changes.

---

## 8) Risk and evolution pages

- `/dashboard`
  - current global risk score
  - recent global trend points
  - links to projects/targets
- `/projects/<id>`
  - current project risk score
  - top risky targets (latest target scores)
- `/targets/<id>`
  - current target risk score
  - open findings list with severity, instance count, last seen
  - link to evolution views
- `/targets/<id>/evolution`
  - risk-over-time chart for that target
  - scan comparison table including risk delta and finding counts
- `/targets/<id>/evolution/<comparison_id>`
  - diff details showing new vs resolved findings

---
## 9) Admin surfaces

Django admin registers:

- core scan models (`Project`, `Target`, `ScanProfile`, `ScanJob`, `RawZapResult`)
- normalized risk models (`Finding`, `FindingInstance`, `RiskSnapshot`)

Use admin to:

- inspect dedup behavior
- tune `risk_weights` in `Setting`
- verify snapshot generation over time

---

## 10) Local development

From this directory:

```bash
cd backend/zapcontrol
```

### Common commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

### Running local server

```bash
python manage.py runserver 0.0.0.0:8000
```

If your local environment is outside docker-compose, ensure DB/Redis hostnames in settings/env resolve correctly.

---

## 11) Migrations added for risk normalization and evolution tracking

The schema for normalized findings/risk snapshots is introduced by:

- `targets/migrations/0004_finding_risksnapshot_findinginstance.py`
- `targets/migrations/0005_scancomparison.py`

Apply with:

```bash
python manage.py migrate
```

---

## 12) Known limits (current scope)

- API scan flow is placeholder
- Risk score is weighted counts (triage signal), not exploitability scoring

---

## 13) Suggested next steps

- add stateful finding status (open/accepted/fixed/false-positive)
- add suppression rules
- add tests for normalization idempotency and snapshot math

