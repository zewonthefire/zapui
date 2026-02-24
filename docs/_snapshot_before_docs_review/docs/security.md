# Security

This document explains ZapUI's security model, trust boundaries, and hardening recommendations.

---

## 1) Trust boundaries

Primary boundaries:

- **Public boundary**: nginx ingress (HTTP/HTTPS).
- **Application boundary**: Django web/worker internal services.
- **Data boundary**: PostgreSQL + Redis internal state stores.
- **Scanner boundary**: internal/external ZAP APIs.
- **Privileged boundary**: optional Ops Agent with Docker socket access.

Understanding and minimizing cross-boundary exposure is the main hardening objective.

---

## 2) Authentication and authorization

- Email-based authentication with custom user model.
- Role model includes `admin`, `security_engineer`, `readonly`.
- Admin-only checks protect operations and node-management surfaces.
- Sensitive operations require password re-confirmation and are audit logged.

---

## 3) Setup-time security controls

- Access is gated by setup middleware until initialization is complete.
- TLS mode can be generated (self-signed) or provided (validated cert/key).
- Production deployments must replace temporary/self-signed certificates with trusted certs.

---

## 4) Secrets and configuration safety

Sensitive values include:

- `DJANGO_SECRET_KEY`,
- database credentials,
- `OPS_AGENT_TOKEN`,
- TLS private keys in `certs/privkey.pem`.

Best practices:

- never commit real secrets,
- rotate secrets regularly,
- restrict file permissions,
- prefer secure secret injection paths in production.

---

## 5) Ops Agent and Docker socket risk

Ops Agent is disabled by default for a reason.

When enabled, the container mounts `/var/run/docker.sock`, which can grant host-equivalent control in many environments.

Mandatory controls if enabling Ops:

- strong random `OPS_AGENT_TOKEN`,
- internal-only network exposure,
- strict admin account controls,
- frequent token rotation,
- active audit review.

---

## 6) Network hardening recommendations

- expose only required public ports,
- keep internal services on private networks,
- restrict host firewall rules to known management sources,
- avoid direct public exposure of DB/Redis/ZAP/Ops services,
- enforce TLS for operator access.

---

## 7) Application hardening checklist

- set strict `DJANGO_ALLOWED_HOSTS`,
- keep dependencies and base images updated,
- use non-default strong credentials,
- keep CSRF/session secure settings enabled in production,
- monitor failed auth and privileged action patterns.

---

## 8) Backup and incident response security

Backups include sensitive data and must be:

- encrypted at rest,
- transferred over secure channels,
- access-controlled with least privilege,
- periodically restore-tested.

Incident response should include immediate secret rotation and audit log review after compromise suspicion.

---

## 9) Security limitations (current scope)

- no built-in enterprise SSO provider integration in current baseline,
- no native finding lifecycle status governance model yet,
- Ops mode remains high-trust and should be used cautiously.
