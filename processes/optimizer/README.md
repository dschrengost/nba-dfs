Optimizer Adapter (Headless)

Purpose
- Headless adapter wrapping a solver entrypoint to produce optimizer artifacts.
- Consumes normalized projections, maps config→constraints, runs solver, writes
  Parquet artifacts and a manifest, and appends to a runs registry.

CLI
- Example:
  - `uv run python -m processes.optimizer --slate-id 20251101_NBA --site DK --config configs/optimizer.yaml --engine cbc --seed 42 --out-root data --tag PRP-2`
  - Add `--verbose` to emit a single-line warning for unknown config keys.

Inputs
- Projections search order (first match wins):
  - `<in_root>/processed/current/projections.parquet`
  - `<in_root>/projections/normalized/<slate_id>.parquet`
  - `<in_root>/projections/normalized/<slate_id>/projections.parquet`
  - `<in_root>/processed/<slate_id>/projections.parquet`
- Override with `--input <path>`.

Config → Constraints
- Pass-through keys supported:
  - `num_lineups`, `max_salary`, `min_salary`, `lock`, `ban`, `exposure_caps`,
    `stacking`, `group_rules`, `ownership_penalty`, `uniques`, `max_from_team`,
    `min_from_team`, `position_rules`, `randomness`, `cp_sat_params`, `preset`,
    `dk_strict_mode`.
- Unknown keys preserved to allow downstream expansion; unsupported keys are ignored by the solver.

Outputs
- `<out_root>/runs/optimizer/<run_id>/lineups.parquet` (optimizer_lineups)
- `<out_root>/runs/optimizer/<run_id>/metrics.parquet` (optimizer_metrics)
- `<out_root>/runs/optimizer/<run_id>/manifest.json` (manifest)
- Appends `<out_root>/registry/runs.parquet`

Notes
- The adapter itself does not import Streamlit. A legacy solver can be used via
  lazy import. Prefer setting `OPTIMIZER_IMPL` to a headless function.
- `export_csv_row` is a preview string in DK slot order (PG,SG,SF,PF,C,G,F,UTIL),
  not an upload-ready DK CSV row; adapters/tooling perform DK export mapping.
  Tests assert header order only.
 
