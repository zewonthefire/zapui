# Reporting Pipeline

## Documentation Changelog
- Date: 2026-02-24
- Added: Report generation and download flow.
- Clarified: HTML/JSON/PDF dependencies.
- Deprecated: None.
- Appendix: N/A (new file).

## Reporting flow
```mermaid
flowchart LR
  A["Completed ScanJob"] --> B["generate_scan_report"]
  B --> C["Serialize normalized findings"]
  C --> D["Write HTML + JSON artifacts"]
  D --> E["POST /render to PDF service"]
  E --> F["Store PDF file"]
  F --> G["/scans/<id>/report/:format (html|json|pdf)"]
```

## Checks
```bash
docker compose logs -f --tail=200 pdf web
```
