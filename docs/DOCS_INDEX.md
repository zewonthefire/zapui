# Documentation Index

## Documentation Changelog
- Date: 2026-02-24
- Added: Full inventory of Markdown documentation and intended purpose.
- Clarified: Which files are canonical for architecture, security, operations, and developer workflows.
- Deprecated: None.
- Appendix: N/A (new file).

## Repository documentation map
- `README.md`: main platform overview, installation entrypoint, and high-level operating model.
- `docs/architecture.md`: service topology, data model, scan lifecycle, and trust boundaries.
- `docs/api.md`: in-product and Ops Agent HTTP endpoints.
- `docs/operations.md`: day-2 runbooks, scaling, restart/rebuild/redeploy flows.
- `docs/security.md`: security posture, risk model, hardening guidance.
- `docs/install.md`: installer and manual installation walkthrough.
- `docs/configuration.md`: environment variables and runtime configuration behavior.
- `docs/scanning.md`: scan profile behavior and end-to-end scan execution sequence.
- `docs/reporting.md`: report generation pipeline (HTML/JSON/PDF).
- `docs/assets-and-evolution.md`: findings normalization, risk snapshots, and scan comparison deltas.
- `docs/CODE_REALITY.md`: canonical facts extracted from code and compose definitions.
- `docs/DOCS_GAPS.md`: gaps and inconsistencies discovered during review.
- `docs/DOCS_QA_CHECKLIST.md`: final multi-pass QA checks.
- `docs/NO_LOSS_REPORT.md`: file-level preservation audit.

## Subfolder READMEs
- `backend/README.md`
- `backend/zapcontrol/README.md`
- `docker/README.md`
- `docker/nginx/README.md`
- `docker/web/README.md`
- `docker/ops/README.md`
- `docker/pdf/README.md`
- `nginx/README.md`
- `scripts/README.md`
