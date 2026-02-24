# Assets and Evolution

## Documentation Changelog
- Date: 2026-02-24
- Added: Asset/finding evolution and scan diff behavior.
- Clarified: New vs resolved finding computation.
- Deprecated: None.
- Appendix: N/A (new file).

## Diffing flow
```mermaid
flowchart TD
  A[Scan N findings] --> C[Comparison Engine]
  B[Scan N+1 findings] --> C
  C --> D[New finding IDs]
  C --> E[Resolved finding IDs]
  C --> F[Risk delta]
  D --> G[Target evolution timeline]
  E --> G
  F --> G
```

## Operator path
- Open target detail: `/targets/<target_id>`.
- Open evolution chart: `/targets/<target_id>/evolution`.
- Open comparison details from timeline/cards.
