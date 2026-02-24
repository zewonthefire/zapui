# Documentation Gaps and Inconsistencies

## Documentation Changelog
- Date: 2026-02-24
- Added: Gap audit aligned to code-truth review.
- Clarified: Priority fixes and why they matter operationally.
- Deprecated: None.
- Appendix: N/A (new file).

## Gaps identified
1. No single canonical source for compose service names/ports/env defaults.
2. Existing docs lacked explicit mapping for setup middleware and setup lock behavior.
3. Missing dedicated pages for installation, configuration, scanning, reporting, and asset evolution.
4. Ops Agent high-privilege model was described but needed stronger safe-deployment runbooks.
5. No explicit no-loss audit artifact.

## Inconsistencies corrected by enrichment
- Scan API profile (`api_scan`) exists in model but is currently unimplemented in Celery task logic.
- `ops` service is profile-gated (`COMPOSE_PROFILES=ops`) and should not be assumed active.
- Public ingress defaults are `8090` (HTTP) and `443` (HTTPS), driven by `.env`.

## Follow-up recommendations
- Add automated link checking for Markdown docs in CI.
- Add endpoint contract tests for Ops Agent and PDF service.
