# Architecture

## High-level design
ZapUI is a Dockerized security orchestration platform for OWASP ZAP. It combines:
- Django web app (UI + APIs)
- Celery worker/beat (asynchronous scan execution)
- PostgreSQL (state + historical analytics)
- Redis (queueing)
- Nginx (TLS termination + setup gating)
- OWASP ZAP daemon(s) as internal and/or external scan nodes
- Optional Ops Agent (privileged operational actions)

## Core concepts and relationships
- **Project**: top-level application/business scope.
- **Target/Asset**: concrete URL/service in a project.
- **Zap Node**: scan execution engine endpoint (`internal_managed` or `external`).
- **Scan Profile**: reusable scan policy template.
- **Scan Job**: one execution of profile+target.
- **Finding**: normalized vulnerability (stable identity over time).
- **Risk Snapshot**: weighted score at target/project/global levels.
- **Evolution**: scan-to-scan comparison (`new`, `resolved`, `risk_delta`).

## Runtime flow
1. User creates project, target, and profile.
2. User submits scan job.
3. Celery task selects a node and drives spider/ascan lifecycle via ZAP API.
4. Raw alerts are persisted.
5. Alerts are normalized into findings/instances.
6. Risk snapshots are computed.
7. Evolution diff is generated against previous completed scan.
8. Reports are generated (HTML/JSON/PDF).

## Deployment topology
- Host ports map into nginx (`PUBLIC_HTTP_PORT` -> 8080, `PUBLIC_HTTPS_PORT` -> 8443).
- Nginx forwards to Django (`web:8000`) and serves static/media volumes.
- Internal ZAP is only on compose network by default.
- Optional external nodes can be registered and health-checked.

## Setup wizard gating
Until setup is complete, middleware redirects non-exempt routes to `/setup`.
Nginx also uses `nginx/state/setup_complete` to decide whether HTTP should redirect to HTTPS.

## Operational model
- Default mode: safe baseline, no privileged compose control.
- Ops mode: enable `ops` profile + token, allowing UI-driven restart/rebuild/redeploy/scale workflows.
- Internal ZAP scaling uses compose service scaling and syncs `ZapNode` records.
