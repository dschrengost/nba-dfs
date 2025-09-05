Variant Adapter

- Purpose: Headless adapter wrapping a variant builder to produce variant artifacts from optimizer lineups.
- Inputs: optimizer lineups parquet (schema: `optimizer_lineups`).
- Outputs:
  - `<out_root>/runs/variants/<run_id>/variant_catalog.parquet` (variant_catalog)
  - `<out_root>/runs/variants/<run_id>/metrics.parquet` (variant_metrics)
  - `<out_root>/runs/variants/<run_id>/manifest.json` (manifest)
- Registry: Appends `<out_root>/registry/runs.parquet` with `run_type="variants"`.

CLI

python -m processes.variants \
  --slate-id 20251101_NBA \
  --config configs/variants.yaml \
  --seed 42 \
  --out-root data \
  [--input path/to/optimizer_lineups.parquet] \
  [--from-run <optimizer_run_id>] \
  [--schemas-root path/to/pipeline/schemas] \
  [--no-validate] \
  [--verbose]

Notes

- Deterministic run_id: `YYYYMMDD_HHMMSS_<shortsha>` mixing input SHA + cfg SHA + seed.
- `OPTIMIZER_VARIANT_IMPL=module:function` can override the variant builder import.
- The adapter does not import Streamlit/UI packages.
- `export_csv_row` is a preview string in DK slot order; it is not a DK-uploadable CSV row.
- Input discovery: `--input` path > `--from-run` > registry latest (`run_type=optimizer`); registry must include columns `run_type, slate_id, created_ts`.
- Manifest inputs.role is `optimizer_lineups` for the optimizer-lineups parquet.
- Seed precedence: the adapter passes `seed` as a function argument and also includes `seed` in the `knobs` dict for compatibility. If both are present, the function argument takes precedence.
