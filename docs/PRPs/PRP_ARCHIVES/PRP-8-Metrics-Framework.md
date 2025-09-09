# PRP-8: Metrics Framework

## Purpose
Introduce a metrics framework that computes and validates lineup- and portfolio-level statistics after GPP simulations.  
Goal: standardized, schema-validated metrics artifacts for evaluation and downstream API/UI use.

## Scope
- **Module**: `processes/metrics/`
- **Schemas**:
  - `pipeline/schemas/metrics.schema.yaml` — defines metric rows
  - `pipeline/schemas/portfolio.schema.yaml` — defines portfolio-level summaries
- **Inputs**:
  - `sim_results.parquet` (from PRP-5)
  - `field.parquet` (from PRP-4)
  - `lineups.parquet` (from PRP-2)
- **Outputs**:
  - `metrics.parquet` — per-lineup and per-portfolio metrics
  - Manifest + registry append (run_type=`metrics`)
- **CLI**:
  - `uv run python -m processes.metrics --from-sim <run_id> --out-root data`
  - Options for: per-lineup metrics, portfolio metrics, aggregated metrics

## Key Features
- **Lineup-level**: ROI, EV, ownership leverage, duplication risk
- **Portfolio-level**: Sharpe ratio, Sortino ratio, exposure coverage, chalk index
- **Validation**: schema-validated before writes
- **Determinism**: run_id = `YYYYMMDD_HHMMSS_<sha8>` from sim + config

## Tests
- Smoke test: valid sim results → metrics written
- Determinism test: same sim/config → same run_id
- Fail-fast: invalid sim results block write
- Golden dataset: tiny sim + expected metrics

## Dependencies
- Requires PRP-5 artifacts (`sim_results`, `sim_metrics`).
- Integrates with orchestrator (PRP-6).
