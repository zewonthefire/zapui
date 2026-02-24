# API and Endpoint Reference

This document lists key user-facing and integration-facing endpoints used by ZapUI.

---

## 1) Platform and health

- `GET /health`
  - basic service heartbeat.
- `GET /api/version`
  - returns app version metadata.

---

## 2) Authentication

- `GET /login`
- `POST /login`
- `GET /logout`

Session-based auth is used for UI access.

---

## 3) Setup and core UI

- `GET /setup`
- `POST /setup`
- `GET /dashboard`

Setup endpoint is multi-step and stateful.

---

## 4) Operations and node management

- `GET /ops/overview`
- `GET /ops/actions`
- `GET /ops/logs/<service>`
- `GET /zapnodes`
- `POST /zapnodes`

Privileged actions require admin authorization and password confirmation in UI flows.

---

## 5) Scanning and analysis routes

- `GET /profiles`
- `POST /profiles`
- `GET /scans`
- `POST /scans`
- `GET /scans/<id>`
- `GET /scans/<id>/report/<html|json|pdf>`
- `GET /reports`
- `GET /projects/<id>`
- `GET /targets/<id>`
- `GET /targets/<id>/evolution`
- `GET /targets/<id>/evolution/<comparison_id>`

---

## 6) Internal OWASP ZAP API usage

ZapUI calls these ZAP endpoints on configured nodes:

- `/JSON/core/view/version/`
- `/JSON/spider/action/scan/`
- `/JSON/spider/view/status/`
- `/JSON/ascan/action/scan/`
- `/JSON/ascan/view/status/`
- `/JSON/core/view/alerts/`

Optional API key is forwarded when node key is configured.

---

## 7) Optional Ops Agent API usage

When enabled, backend integrates with ops endpoints:

- `GET /compose/services`
- `GET /compose/logs/{service}`
- `POST /compose/restart/{service}`
- `POST /compose/rebuild`
- `POST /compose/redeploy`
- `POST /compose/scale`
- `GET /compose/env-summary`

Authentication uses `X-OPS-TOKEN`.

---

## 8) Notes

- Most endpoints are UI-oriented and session-authenticated.
- Public unauthenticated routes are intentionally minimal.
- Route behavior can be setup-gated until initialization completes.
