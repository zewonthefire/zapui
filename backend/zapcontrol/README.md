# ZapControl Backend Guide

This guide documents the Django backend in `backend/zapcontrol` in depth.
It is intended for engineers who operate, extend, or troubleshoot ZapUI.

---

## 1) Executive summary

ZapControl is the application engine behind ZapUI. It:

- authenticates users and enforces role-aware access,
- gates access behind the first-run setup wizard until initialization is complete,
- orchestrates OWASP ZAP scans asynchronously with Celery,
- stores raw scan outputs and normalizes them into long-lived findings,
- computes weighted risk snapshots at target, project, and global scope,
- computes evolution diffs between consecutive completed scans,
- generates persisted reports (HTML, JSON, PDF),
- provides operational pages and audit logging for sensitive actions.

In short: it transforms scanner API calls into an auditable, historical security control plane.

---

## 2) Backend scope and responsibilities

The backend is split into three Django apps:

- `accounts`
  - custom user model using email login,
  - login/logout views,
  - role metadata.
- `core`
  - setup wizard state and persistence,
  - dashboard and version endpoints,
  - operations overview/actions/log views,
  - settings and audit log models,
  - setup-gating middleware.
- `targets`
  - project/target inventory,
  - scan profile and scan job lifecycle,
  - zap node inventory and health checks,
  - raw alert storage,
  - findings normalization,
  - risk snapshots and scan comparisons,
  - report generation and downloads.

---

## 3) Runtime architecture

### Django process

- Entrypoint: `manage.py`
- Settings package: `zapcontrol.settings`
- URL root: `zapcontrol.urls`
- Gunicorn serves the web app in containers.

### Async execution

- Celery worker executes scan orchestration jobs.
- Celery beat is available for schedule-driven workflows.
- Redis is used for broker/result backends.

### Persistence

- PostgreSQL is the primary state store.
- SQLite is supported for local testing/development (`DJANGO_DB_ENGINE=sqlite`).

### Service integrations

- OWASP ZAP JSON API for scan execution and alerts retrieval.
- Internal PDF service for HTML-to-PDF report rendering.
- Optional Ops Agent for compose-driven operational actions.

---

## 4) Setup wizard and request gating

### Wizard persistence model

Setup state is persisted in `core.SetupState`:

- `is_complete`: global completion flag,
- `current_step`: active wizard step,
- `wizard_data`: accumulated setup payload,
- additional operational notes fields.

### Middleware behavior

`core.middleware.SetupWizardMiddleware` redirects requests to `/setup` while setup is incomplete, except for exempt routes (health/static/media/version/setup).

This guarantees users cannot operate an uninitialized instance.

---

## 5) Authentication, identity, and authorization

### User model

- Custom `accounts.User` replaces username with unique email.
- Role values:
  - `admin`
  - `security_engineer`
  - `readonly`

### Access control patterns

- Login required for core application pages.
- Admin-only checks are enforced in operations/zap node management paths.
- Sensitive operations require password re-confirmation.
- Audit events are written to `core.OpsAuditLog` for privileged actions.

---

## 6) Domain model (security and scanning)

The main domain models are in `targets.models`.

### Inventory and execution entities

- `Project`: organizational grouping of assets.
- `Target`: scan endpoint/environment in a project.
- `ZapNode`: scan engine endpoint (internal managed or external).
- `ScanProfile`: reusable scan strategy template.
- `ScanJob`: a concrete execution instance.
- `RawZapResult`: unmodified alerts payload for a completed scan.

### Findings entities

- `Finding`
  - dedup key: `(target, zap_plugin_id, title)`,
  - tracks first seen, last seen, severity, and instance count.
- `FindingInstance`
  - concrete occurrence for a specific scan,
  - uniqueness across finding + scan + location/evidence attributes.

### Risk and evolution entities

- `RiskSnapshot`
  - required `scan_job`,
  - optional `target` and `project` for scope,
  - stores weighted score and severity counts.
- `ScanComparison`
  - links previous and current completed scans for a target,
  - stores new/resolved finding id lists and risk delta.

### Reporting entity

- `Report`
  - one-to-one with `ScanJob`,
  - stores HTML/JSON/PDF report files.

---

## 7) Scan orchestration lifecycle

Entry task: `targets.tasks.start_scan_job`.

### Flow

1. Resolve scan node (profile-pinned or scheduler-selected).
2. Move job from `pending` to `running`.
3. Optionally execute spider phase and poll completion.
4. Execute active scan and poll completion.
5. Fetch raw alerts.
6. Persist `RawZapResult`.
7. Normalize alerts into findings and finding instances.
8. Create risk snapshots (target/project/global).
9. Compute scan comparison against previous completed scan.
10. Generate report artifacts.
11. Mark job `completed` or `failed` with reason.

### Error and retry behavior

- Network/transient failures are retried with Celery autoretry settings.
- Non-retryable failures transition job to `failed` with captured error message.

---

## 8) Node selection and health model

Node selection strategy:

1. If profile has a pinned node, that node must be enabled and healthy.
2. Else prefer enabled+healthy node with lowest active running jobs.
3. Else fallback to first enabled node.
4. If none enabled, orchestration fails.

Node health test targets:

- `/JSON/core/view/version/` with optional API key.
- Persisted health metadata includes status, latency, version, and timestamp.

---

## 9) Findings normalization model

Normalization logic resides in `targets/risk.py`.

Key rules:

- normalize risk labels to canonical severities (`High`, `Medium`, `Low`, `Info`),
- deduplicate at finding level by target + plugin + title,
- update recurrence metadata (`last_seen`),
- persist granular finding instances per scan/evidence,
- maintain `instances_count` consistency.

This converts scanner-event streams into stable vulnerability history.

---

## 10) Risk scoring model

Default weights:

- High = 10
- Medium = 5
- Low = 2
- Info = 1

Optional override source:

- `core.Setting` with key `risk_weights`.

Scoring formula per scope:

`score = Σ(count_by_severity[level] * weight[level])`

Generated scopes on each completed scan:

- target snapshot,
- project snapshot,
- global snapshot.

---

## 11) Evolution diff computation

Function: `create_scan_comparison(scan_job)`.

Algorithm:

1. Find previous completed scan for same target.
2. Build finding id sets from finding instances for previous/current scans.
3. Compute set deltas:
   - `new = current - previous`
   - `resolved = previous - current`
4. Compute `risk_delta = current_target_risk - previous_target_risk`.
5. Upsert `ScanComparison` row.

Outcome: a deterministic scan-over-scan change log.

---

## 12) Reporting pipeline (HTML, JSON, PDF)

Reports are generated after successful scan completion.

### Output formats

- HTML for human-readable detail,
- JSON for machine ingestion,
- PDF for sharing and archival.

### Pipeline

1. Build report payload from job/findings/risk data.
2. Render HTML template.
3. Serialize JSON payload.
4. Send HTML to PDF service (`POST /render` on `PDF_SERVICE_URL`).
5. Save files and create/update `Report` record.

### Storage paths (under `MEDIA_ROOT`)

- `reports/html/scan-<id>.html`
- `reports/json/scan-<id>.json`
- `reports/pdf/scan-<id>.pdf`

### Download routes

- `/scans/<id>/report/html`
- `/scans/<id>/report/json`
- `/scans/<id>/report/pdf`
- `/reports`

---

## 13) User-facing backend routes (high-value)

- Setup and platform:
  - `/setup`
  - `/health`
  - `/api/version`
- Authentication:
  - `/login`
  - `/logout`
- Core and operations:
  - `/dashboard`
  - `/ops/overview`
  - `/ops/actions`
  - `/ops/logs/<service>`
  - `/zapnodes`
- Scanning and analysis:
  - `/profiles`
  - `/scans`
  - `/scans/<id>`
  - `/projects/<id>`
  - `/targets/<id>`
  - `/targets/<id>/evolution`
  - `/targets/<id>/evolution/<comparison_id>`

---

## 14) Administration surfaces

Django admin provides diagnostic and governance access to:

- scan entities (`Project`, `Target`, `ScanProfile`, `ScanJob`, `RawZapResult`),
- analysis entities (`Finding`, `FindingInstance`, `RiskSnapshot`, `ScanComparison`, `Report`),
- control entities (`Setting`, `SetupState`, `OpsAuditLog`, users/roles).

Typical admin workflows:

- verify normalization behavior,
- tune risk weights,
- inspect job failures and node health,
- review operations audit trail.

---

## 15) Local development and maintenance

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

### Local server

```bash
python manage.py runserver 0.0.0.0:8000
```

For non-compose local runs, ensure environment values for DB/Redis/PDF service hosts are resolvable.

---

## 16) Key schema migrations

Notable migrations for findings/risk/evolution/reporting include:

- `targets/migrations/0004_finding_risksnapshot_findinginstance.py`
- `targets/migrations/0005_scancomparison.py`
- `targets/migrations/0006_report.py`

Apply with:

```bash
python manage.py migrate
```

---

## 17) Existing automated coverage

Current tests include:

- setup gating behavior,
- login and role restrictions,
- adding/testing external zap node connectivity (mocked),
- scan lifecycle orchestration with mocked ZAP client,
- evolution diff (`new/resolved/risk_delta`) checks.

Run with:

```bash
DJANGO_DB_ENGINE=sqlite python manage.py test
```

---

## 18) Known limitations

- `api_scan` path is a placeholder and intentionally returns not implemented behavior.
- risk score is weighted-count based and not a full exploitability framework.
- finding workflow states (accepted/fixed/false-positive) are not yet first-class domain state.

---

## 19) Recommended next steps

- add finding lifecycle states and suppression workflows,
- add policy-driven SLAs and compliance reporting,
- enrich risk model with asset criticality and CVSS-like dimensions,
- expand automated tests for normalization idempotency and comparison invariants,
- add workload/performance tests for async orchestration.

---

## 20) Related documentation

- Root onboarding and operator manual: `README.md`
- System architecture: `docs/architecture.md`
- Security model and hardening: `docs/security.md`
- Operations runbook: `docs/operations.md`
- Endpoint inventory: `docs/api.md`
