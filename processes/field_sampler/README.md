# Field Sampler Adapter

Headless adapter to build a representative contest field from a variant catalog
(and optionally optimizer base lineups). It validates artifacts against the
house schemas and appends to the run registry. No UI; implementation is loaded
dynamically.

Quick start
- Create or point to a `variant_catalog.parquet` for a slate.
- Run the CLI:
  `uv run python -m processes.field_sampler --slate-id 20251101_NBA --config configs/field.yaml --seed 42 --out-root data --input path/to/variant_catalog.parquet`

Discovery (inputs)
- `--input`: explicit `variant_catalog.parquet` path.
- `--from-run <variants_run_id>`: resolves `<out_root>/runs/variants/<run_id>/artifacts/variant_catalog.parquet`.
- Latest `run_type="variants"` for the `slate_id` in registry when neither is provided.
- `--inputs p1 p2 ...`: merge multiple catalogs.

Implementation loader
- Provide `FIELD_SAMPLER_IMPL=module:function` to specify a sampler.
- The adapter calls `fn(catalog_df: pd.DataFrame, knobs: dict, seed: int)` and
  expects either `list[dict]` entrants or `(list[dict], telemetry)`.
  Each entrant must include: `origin` (variant|optimizer|external), `players`
  (8 DK IDs), and `export_csv_row`. Optional: `variant_id`/`lineup_id`, `weight`.

Outputs
- `runs/field/<run_id>/artifacts/field.parquet` — schema `field`.
- `runs/field/<run_id>/artifacts/metrics.parquet` — schema `field_metrics`.
- `runs/field/<run_id>/manifest.json` — run metadata.
- Registry append to `registry/runs.parquet` with `primary_outputs=[field.parquet]`.

Validation & determinism
- Validates every row of `field` and `field_metrics` prior to any writes.
- Deterministic `run_id = YYYYMMDD_HHMMSS_<shorthash>` over input SHA(s) +
  resolved config + seed.

Config → knobs (initial)
- `field_size`, `source_mix`, `sampling_mode`, `ownership_curve`, `diversity`,
  `team_limits`, `de-dup`, `seed`, plus any extras preserved under `extras`.
