# Run Registry

## Purpose
- Central, append‑only index of runs and their primary outputs.
- Written by modules (here: `pipeline.ingest`) after successful validation and artifact writes.

## Storage
- Path: `{out_root}/registry/runs.parquet` (default `data/registry/runs.parquet`).
- Append semantics: one row per run (idempotence by `run_id` is the caller’s responsibility).

## Schema (columns)
- `run_id` (str): `YYYYMMDD_HHMMSS_<shortsha>` minted at runtime.
- `run_type` (str): one of `ingest|optimizer|variants|field|sim`.
- `slate_id` (str): like `20251101_NBA`.
- `status` (str): `success|failed|running|unknown`.
- `primary_outputs` (list[str]): paths to primary artifacts (e.g., normalized projections parquet).
- `metrics_path` (str): path to run metrics JSON (may not exist yet at write time).
- `created_ts` (UTC ISO): creation timestamp of the registry row.
- `tags` (list[str]): optional labels.

Authoritative schema: `pipeline/schemas/runs_registry.schema.yaml`.

## Relationship to Manifest
- Each run also writes `{out_root}/runs/{run_type}/{run_id}/manifest.json` (schema: `manifest.schema.yaml`).
- The manifest captures detailed `inputs[]` (with `content_sha256`) and `outputs[]` with `kind` and `path`.
- Registry serves quick discovery; manifest is the full lineage record.

## How `run_id` Is Minted
- Format: `YYYYMMDD_HHMMSS_<shortsha>` in UTC.
- Seed material (for `ingest`): `f"{slate_id}|{source}|{first12(projections_sha256)}"`.
- Short hash: first 8 chars of a SHA‑1 over the seed material.

## Query Examples
Using pandas to fetch the latest successful run for a slate:
```
import pandas as pd
reg = pd.read_parquet("data/registry/runs.parquet")
latest = (
    reg.query("slate_id == '20251101_NBA' and run_type == 'ingest' and status == 'success'")
       .sort_values("created_ts")
       .tail(1)
)
run_id = latest.iloc[0]["run_id"] if not latest.empty else None
primary_norm = latest.iloc[0]["primary_outputs"][0] if not latest.empty else None
print(run_id, primary_norm)
```

To list most recent N runs per `slate_id`:
```
N = 5
recent = (
    reg.sort_values(["slate_id", "created_ts"]).groupby("slate_id", as_index=False).tail(N)
)
```

## Operational Notes
- Writers should validate against `runs_registry.schema.yaml` before appending (ingest does this by default).
- Registry is not a job queue; it is a log for discovery and auditing.
- Downstream processes should tolerate duplicate `slate_id` entries and select by recency or tags.

