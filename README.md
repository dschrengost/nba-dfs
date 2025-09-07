# NBA-DFS

Data pipeline and tools for NBA Daily Fantasy Sports.

## Structure
- `pipeline/` — ingestion, normalization, registry, schemas
- `processes/` — optimizer, variant builder, field sampler, simulator
- `app/` — unified dash
- `data/` — parquet store (ignored from git)
- `docs/` — design notes, schemas, PRPs

## Optimizer QA (fixtures)
- Generate merged snapshot from DK CSVs: `node scripts/make-fixture-snapshot.mjs 2024-01-15`
- Run headless greedy sampler: `node scripts/qa-opt-fixture.mjs 2024-01-15`
