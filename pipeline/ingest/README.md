# Ingest Front Door (PRP‑1)

## Overview
- Purpose: Normalize raw projection CSVs into a canonical parquet, record lineage and write a run manifest + registry row.
- Inputs: `--projections` (CSV), `--player-ids` (CSV), `--mapping` (YAML header map).
- Outputs under `--out-root` (default `data/`):
  - `reference/players.parquet`: normalized players reference.
  - `projections/raw/{slate_id}__{source}__{uploaded_ts}.parquet`: raw import snapshot.
  - `projections/normalized/{slate_id}__{source}__{uploaded_ts}.parquet`: canonical projections.
  - `runs/ingest/{run_id}/manifest.json`: run manifest (schema: `manifest.schema.yaml`).
  - `registry/runs.parquet`: append‑only registry (schema: `runs_registry.schema.yaml`).

## CLI Usage
Run as a module or call `main()` from Python.

- Module: `python -m pipeline.ingest --help`
- Entry point: `pipeline.ingest.cli:main`

Flags (exact):
- `--slate-id` (required): Slate id like `20251101_NBA`.
- `--source` (required): Source tag, e.g. `manual`, `primary`, `other` or a custom name.
- `--projections` (required): Path to projections CSV.
- `--player-ids` (required): Path to player IDs CSV.
- `--mapping` (required): Path to YAML header mapping.
- `--out-root` (default: `data`): Output root folder.
- `--tag` (repeatable): Freeform labels stored on manifest and registry.
- `--validate` / `--no-validate` (default validate on): Toggle JSON‑Schema validation at runtime.
- `--schemas-root` (default: `pipeline/schemas`): Alternative schemas folder (useful for tests).

Example (uses repo fixtures; safe to copy‑paste):
```
python -m pipeline.ingest \
  --slate-id 20251101_NBA \
  --source primary \
  --projections tests/fixtures/projections_sourceA.csv \
  --player-ids tests/fixtures/player_ids.csv \
  --mapping pipeline/ingest/mappings/example_source.yaml \
  --out-root /tmp/nba_dfs_out \
  --tag PRP-1
```
This prints a preview and lists written artifacts.

## Mapping Catalog
Location: `pipeline/ingest/mappings/*.yaml`

Format (YAML):
```
name: example_source
map:
  # source_header: canonical_field
  DK_ID: dk_player_id
  Name: name
  Team: team
  Pos: pos
  Salary: salary
  Minutes: minutes
  FP: proj_fp
  Ceil: ceil_fp
  Floor: floor_fp
  Own: own_proj
```
Notes:
- Canonical fields used by the normalizer: `dk_player_id`, `name`, `team`, `pos`, `salary`, `minutes`, `proj_fp` (+ optional `ceil_fp`, `floor_fp`, `own_proj`).
- Coercions: `salary` → int (strips `$` and commas); numeric fields → float; `team` uppercased; `pos` uppercased and normalized as `A/B`.
- Unknown columns are ignored for modeling but tracked in lineage.

## Priority Logic
When multiple rows exist for a `dk_player_id`, normalization applies a deterministic dedupe:
- Sort by `updated_ts` ascending and keep the last row → latest timestamp wins.
- For equal `updated_ts`, apply source precedence: `manual` > `primary` > `other` (lower index wins the tie).

## Lineage and Content Hashes
Each normalized row includes a `lineage` object with:
- `mapping`: the header mapping used.
- `source_fields`: ordered list of source headers present.
- `content_sha256`: SHA‑256 of the raw projections CSV at ingest time.
The manifest also captures `inputs[]` with `path` and `content_sha256` for players CSV, projections CSV, and the mapping file.

## Output Paths and Naming
- Raw and normalized filenames: `{slate_id}__{source}__{uploaded_ts}.parquet`, where `uploaded_ts` is UTC ISO `YYYY‑MM‑DDTHH:mm:ss.000Z`.
- Players reference: `reference/players.parquet`.
- Run folder: `runs/ingest/{run_id}` with `manifest.json`.
- Registry: `registry/runs.parquet` appended per run.

`run_id` format: `YYYYMMDD_HHMMSS_<shortsha>` in UTC. The short hash derives from a stable seed: `f"{slate_id}|{source}|{first12(projections_sha)}"`.

## Validation Behavior
- With `--validate` (default), the CLI validates the manifest and a sample registry row against JSON‑Schemas in `--schemas-root`.
- On any validation error, the process exits non‑zero and writes nothing (no parquet, no manifest, no registry row).
- Use `--no-validate` to bypass schema checks (not recommended in CI).

## Troubleshooting
- Schema failure: run with `--schemas-root pipeline/schemas` and ensure your `slate_id`, `run_type`, and timestamps match the schema. Errors are printed to stderr with context.
- Mapping error: `Mapping file ... missing 'map' or 'mapping' dict` → ensure your YAML has a `map:` mapping.
- Unknown headers: harmless; they are ignored for modeling but preserved in `lineage.source_fields`.
- Parquet engine: requires `pyarrow` or `fastparquet` via pandas. If missing, install optional parquet deps.
- No artifacts written: occurs when validation fails or paths are unwritable; check exit code and stderr.

## Quick Test With Fixtures
Two sources are included for testing precedence and normalization:
```
python -m pipeline.ingest \
  --slate-id 20251101_NBA \
  --source primary \
  --projections tests/fixtures/projections_sourceA.csv \
  --player-ids tests/fixtures/player_ids.csv \
  --mapping pipeline/ingest/mappings/example_source.yaml \
  --out-root /tmp/nba_dfs_out
```

Then repeat with `--source manual` and `tests/fixtures/projections_sourceB.csv` to simulate tie‑break scenarios.

