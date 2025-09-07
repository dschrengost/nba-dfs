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

## Python Optimizer (CP-SAT by default)

- Requires Python 3.11+ and `uv` package manager.
- Install deps: `uv sync`
- Runtime toggle:
  - `DFS_SOLVER_MODE=python` (default) runs the Python CLI via `uv`.
  - `DFS_SOLVER_MODE=sampler` uses the in-browser greedy fallback.
- Troubleshooting:
  - If CP-SAT (OR-Tools) is not available, the backend falls back to CBC (pulp).
  - Ensure `uv` is on your PATH and `uv run python scripts/pyopt/optimize_cli.py` works locally.
