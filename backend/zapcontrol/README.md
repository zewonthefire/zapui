# ZapControl Backend Guide


## Documentation Changelog
- Date: 2026-02-24
- Added: Code-verified operational details, commands, and cross-links.
- Clarified: Security posture, runtime behavior, and service boundaries.
- Deprecated: None in this pass.
- Appendix: N/A (no original content removed).

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

Setup note for internal ZAP API key application:
- during step 4, if Ops key reapply returns HTTP 500 while an existing `internal_zap_api_key` is already stored, the wizard now reports a non-blocking warning and keeps the existing key.

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

---

## 2026 Documentation Enrichment

### Code-verified quick commands
```bash
# Validate compose configuration
docker compose config

# Show running services
docker compose ps

# Tail main application logs
docker compose logs -f --tail=200 web worker beat nginx
```

### Related docs
- Root entrypoint: `README.md`
- Canonical runtime facts: `docs/CODE_REALITY.md`
- Validation checklist: `docs/DOCS_QA_CHECKLIST.md`

No original content removed in this file.

---

## Assets module quickstart (inventory, raw results, comparisons)

### Install & run

```bash
cd backend/zapcontrol
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DJANGO_DB_ENGINE=sqlite python manage.py migrate
DJANGO_DB_ENGINE=sqlite python manage.py runserver
```

### Ingest a ZAP JSON report

```bash
DJANGO_DB_ENGINE=sqlite python manage.py ingest_zap_json \
  --project demo \
  --target Main \
  --profile default \
  --node node-1 \
  --file /path/to/result.json
```

### Assets pages

- `/assets/` → Assets Inventory
- `/assets/<id>/` → Asset Detail tabs (Overview / Findings / Risk / Scans / Raw / Comparisons)
- `/assets/raw/` → Global raw ZAP JSON viewer
- Inventory auto-bootstrap: if legacy data exists without `Asset` rows, opening `/assets/` backfills minimal asset rows from existing targets/findings.
- Raw results viewer renders both a human-readable alerts table and pretty-printed JSON; it falls back to `raw_alerts` when legacy rows have empty `payload`.
- `/assets/comparisons/` → Global scan comparisons

### Context APIs

- `/api/context/projects`
- `/api/context/targets?project_id=`
- `/api/context/assets?target_id=`
- `/api/context/nodes`
- `/api/context/profiles?project_id=`
- `/api/context/scans?target_id=&range=`

---

## 21) Administration module (Users/Groups, ZAP Nodes/Pools, Settings, Audit)

### Install / migrate / run

```bash
cd backend/zapcontrol
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DJANGO_DB_ENGINE=sqlite python manage.py migrate
DJANGO_DB_ENGINE=sqlite python manage.py createsuperuser
DJANGO_DB_ENGINE=sqlite python manage.py bootstrap_admin_roles
DJANGO_DB_ENGINE=sqlite python manage.py runserver
```

### Administration URLs

- UI namespace: `/administration/`
  - `/administration/users/`
  - `/administration/groups/`
  - `/administration/nodes/`
  - `/administration/pools/`
  - `/administration/settings/`
  - `/administration/audit/`
- API namespace: `/api/admin/`
  - `users`, `groups`, `nodes`, `pools`, `settings`, `audit`

### Bootstrap and assign baseline groups

```bash
DJANGO_DB_ENGINE=sqlite python manage.py bootstrap_admin_roles
DJANGO_DB_ENGINE=sqlite python manage.py shell -c "from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; u=get_user_model().objects.get(email='admin@example.com'); u.groups.add(Group.objects.get(name='admin'))"
```

Baseline groups:

- `superadmin` (all permissions across the platform)
- `admin` (full Administration access)
- `scanner` (scan configuration + ZAP nodes/pools + audit read)
- `auditor` (read-only audit access)
- `assets_management` (assets/findings/raw-results/report access groups)

> A user can belong to **multiple groups** at once (e.g., `scanner` + `assets_management`).

### Add a ZapNode and run healthcheck

1. Open `/administration/nodes/` and create node with base URL + API key.
2. Use **Test connection** action (or API: `POST /api/admin/nodes/<id>/healthcheck/`).
3. Verify `health_status`, `last_seen_at`, and audit record in `/administration/audit/`.

### Retention settings and purge command

- Edit retention knobs in `/administration/settings/`:
  - `retention_days_raw_results`
  - `retention_days_findings`
  - `retention_days_audit`
- Execute purge manually:

```bash
DJANGO_DB_ENGINE=sqlite python manage.py purge_retention
```

This deletes old `AuditEvent`, `RawZapResult`, and `Report` rows based on configured retention, and writes a system audit event (`action=purge_retention`).
