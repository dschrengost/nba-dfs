Metrics Framework (PRP-8)

Purpose
- Compute standardized, schema-validated metrics artifacts for evaluation and downstream use.

Inputs
- References an existing sim run via `--from-sim <run_id>`.
- Discovers inputs from the sim run manifest (field and contest).

Outputs
- `metrics.parquet` under `runs/metrics/<run_id>/artifacts/` (run-scoped aggregates).
- `manifest.json` (validated) and registry append (`registry/runs.parquet`).

CLI
- Run: `uv run python -m processes.metrics --from-sim <run_id> --out-root data`
- Options:
  - `--schemas-root`: override schema directory (defaults to repo `pipeline/schemas`).
  - `--seed`: deterministic salt; included in run_id hash.
  - `--tag`: optional string tag recorded in manifest/registry.
  - `--verbose`: print discovery and computed metrics summary.

Contracts
- Validates against:
  - `pipeline/schemas/metrics.schema.yaml` (run-level aggregates: ROI, Sharpe, Sortino, duplication risk, entropy).
  - `pipeline/schemas/manifest.schema.yaml` and `pipeline/schemas/runs_registry.schema.yaml` prior to any write.
- Deterministic `run_id`: `YYYYMMDD_HHMMSS_<sha8>` where hash is derived from sim run and inputs.

Notes
- Duplication risk and entropy are computed from the field input (lineup strings). If unavailable, they default to 0.0.
- ROI/Sharpe/Sortino use contest `entry_fee` from sim’s contest input; defaults to 20 when not present.

