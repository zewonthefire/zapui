# Scanning Lifecycle

## Documentation Changelog
- Date: 2026-02-24
- Added: End-to-end transaction flow and failure states.
- Clarified: Node selection and profile behavior.
- Deprecated: None.
- Appendix: N/A (new file).

## Transaction sequence
```mermaid
sequenceDiagram
  participant U as User
  participant W as Django Web
  participant C as Celery Worker
  participant Z as ZAP Node
  participant DB as PostgreSQL

  U->>W: Create ScanJob (/scans)
  W->>DB: Save status=pending
  W->>C: start_scan_job.delay(id)
  C->>DB: Select node + set running
  C->>Z: spider/action/scan (optional)
  C->>Z: ascan/action/scan
  C->>Z: core/view/alerts
  C->>DB: RawZapResult + findings + snapshots + comparison
  C->>DB: Report records/files
  C->>DB: status=completed or failed
```

## Practical checks
```bash
docker compose logs -f --tail=200 worker
```
