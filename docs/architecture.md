# Architecture

This document describes ZapUI's technical architecture, service boundaries, and core runtime flows.

---

## 1) Design goals

ZapUI is designed to provide:

- a deployable single-stack security control plane,
- clear separation of ingress/app/async/data concerns,
- support for both internal and external scan execution nodes,
- historical analysis beyond single scan payloads,
- optional privileged operations mode with explicit risk boundaries.

---

## 2) System components

### Ingress

- `nginx`
  - terminates TLS,
  - proxies requests to `web`,
  - switches routing behavior based on setup completion flag.

### Application

- `web` (Django + Gunicorn)
  - serves UI and endpoints,
  - executes setup flow,
  - stores and queries domain data,
  - triggers async scan jobs.

### Async workers

- `worker` (Celery)
  - orchestrates scan lifecycle and post-processing.
- `beat` (Celery beat)
  - reserved for scheduled workflows.

### Data services

- `db` (PostgreSQL): primary persistence.
- `redis`: queue broker/result backend.

### Security scanners

- `zap` service for internal managed node(s),
- external ZAP nodes can be added via UI and tested.

### Reporting

- `pdf` internal microservice renders HTML reports to PDF.

### Optional operations plane

- `ops` service (profile-gated) provides controlled compose actions.

---

## 3) Network and port model

Host ports map to nginx:

- `PUBLIC_HTTP_PORT` -> `nginx:8080`
- `PUBLIC_HTTPS_PORT` -> `nginx:8443`

Internal services communicate over the compose network.
ZAP, DB, Redis, PDF, and Ops are not intended for direct public exposure.

---

## 4) Setup lifecycle architecture

Two layers enforce setup behavior:

1. Django middleware redirects non-exempt requests to `/setup` while setup incomplete.
2. Nginx entrypoint checks `nginx/state/setup_complete` to decide HTTP redirect behavior.

This dual model provides both app-level and ingress-level setup safety.

---

## 5) Scan execution architecture

### Request-to-execution path

1. user submits job via `/scans`,
2. Django persists `ScanJob` and enqueues Celery task,
3. worker selects node and orchestrates spider/active phases,
4. worker stores raw results,
5. normalization/risk/evolution/reporting pipeline runs,
6. job status transitions to completed or failed.

### Node strategy

- profile-pinned healthy node preferred,
- otherwise healthy least-loaded node,
- fallback enabled node,
- hard failure when none available.

---

## 6) Data and analytics architecture

Pipeline layers:

- **Raw layer**: `RawZapResult` (unaltered scanner output),
- **Normalized layer**: `Finding` + `FindingInstance`,
- **Scoring layer**: `RiskSnapshot` across scopes,
- **Evolution layer**: `ScanComparison` for diff and trend,
- **Reporting layer**: `Report` artifacts (HTML/JSON/PDF).

This layered model allows auditability and reproducible analytics.

---

## 7) Privileged operations architecture

Ops functionality is intentionally optional and profile-gated.

When enabled:

- Django calls Ops Agent with token-authenticated requests,
- Ops Agent validates service names/actions,
- compose operations are executed against the project.

This model centralizes risky actions while preserving default-safe deployment.

---

## 8) Failure domains

Typical failure boundaries:

- ingress/TLS issues (`nginx` + cert material),
- async queue issues (`worker`/`redis`),
- scan backend availability (`zap` nodes),
- persistence failures (`db`),
- report rendering failures (`pdf` service).

Operational runbooks should isolate checks by boundary.

---

## 9) Scalability notes

Current scaling model:

- horizontal scaling of internal ZAP via compose replicas,
- worker throughput tied to Celery worker resources,
- DB/Redis are single service instances unless externally managed.

Future scaling can externalize DB/queue and add worker replicas.
