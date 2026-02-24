# Security

## Security boundaries
- Public ingress is nginx (HTTP/HTTPS).
- Django services are internal to compose network.
- ZAP API is not host-exposed by default.
- Database/Redis are internal services.

## Authentication and authorization
- Custom user model with email login.
- Built-in roles: `admin`, `security_engineer`, `readonly`.
- Admin-only operations pages enforce role checks + password re-confirmation for sensitive actions.

## TLS model
- Nginx expects `certs/fullchain.pem` + `certs/privkey.pem`.
- Temporary self-signed cert is generated at startup if missing.
- Production must replace with trusted certificates and strong key management.

## Ops Agent risk warning
When enabled, Ops Agent mounts Docker socket and project directory. This is privileged and can control compose services.

Hard requirements if enabling Ops Agent:
- Keep disabled unless needed.
- Use strong `OPS_AGENT_TOKEN`.
- Restrict internal network access to ops service.
- Limit admin account access.
- Monitor and rotate credentials.

## Docker socket implications
Mounting `/var/run/docker.sock` effectively grants root-equivalent control on the host in many environments. Treat ops container as high trust.

## Data and secrets
- Sensitive values live in `.env` and wizard settings.
- Use secret management/secure env injection for production.
- Backup encryption and access controls are mandatory for compliance.

## Hardening checklist
- Replace default secrets (`DJANGO_SECRET_KEY`, DB passwords, ops token).
- Enforce trusted TLS certs.
- Set strict `DJANGO_ALLOWED_HOSTS`.
- Keep images updated and scan dependencies.
- Use least-privilege networking/firewall policy.
- Restrict who can run installation/ops workflows.
