
# PRP-1: Ingestion & Normalization + Run Registry (SSOT)

## Status
**Planned** — next after PRP-0 Schema Pack.

## Objective
Implement the front door of the pipeline:
1) Upload **Projections CSV** (any source) and **Player IDs CSV**.  
2) Normalize projections to the canonical schema.  
3) Persist artifacts to Parquet with lineage + content hashes.  
4) Emit **run manifests** and register runs in the **Run Registry**.

No business-logic changes to optimizer/variants/field/sim yet — only ingestion, normalization, persistence, and bookkeeping.

---

## Start Bookend — GitHub Actions
Use the PRP Start action to create the feature branch:

```
PRP Start → branch=feature/ingest-normalization
```

(If running manually)
```bash
git checkout -b feature/ingest-normalization
git push -u origin feature/ingest-normalization
```

---

## Scope & Deliverables

### 1) User-facing (thin CLI/UI stubs only)
- **Uploads**
  - `projections.csv` (arbitrary headers)
  - `player_ids.csv` (DK IDs + names/teams/positions)
- **Normalization preview** (tabular print or UI grid placeholder; no styling required)
- **“Materialize” button** to write normalized Parquet + metadata

### 2) Persistence (Parquet/DuckDB)
- Write to the following locations (create folders if absent):
  - `data/reference/players.parquet`
  - `data/projections/raw/<slate_id>__<source>__<uploaded_ts>.parquet`
  - `data/projections/normalized/<slate_id>__<source>__<updated_ts>.parquet`
- Create/append to:
  - `data/registry/runs.parquet` (Run Registry table)
  - `data/runs/ingest/<run_id>/manifest.json` (per-run manifest)

### 3) Schema adherence
- Validate against these PRP‑0 schemas:
  - `players.schema.yaml`
  - `projections_raw.schema.yaml`
  - `projections_normalized.schema.yaml`
  - `manifest.schema.yaml`
  - `runs_registry.schema.yaml`

### 4) Lineage & Priority
- Compute `content_sha256` of uploaded CSVs (raw bytes). Store in `projections_raw` and `lineage.content_sha256` in normalized.
- **Latest wins** per `(slate_id, dk_player_id)` based on `updated_ts` (tie-breaker source order: `manual > primary > other`). Documented and covered by tests.

### 5) Header mapping
- Introduce a **mapping catalog** to transform arbitrary projection sources → canonical fields:
  - Supported canonical columns: `dk_player_id`, `name`, `team`, `pos`, `salary`, `minutes`, `proj_fp`, `ceil_fp`, `floor_fp`, `own_proj`
  - Allow `extras` bag for unknowns (keeps schemas strict via `additionalProperties: false` on the main object).
- Mapping catalog can be simple YAML in `pipeline/ingest/mappings/`:
  - e.g., `source_abc.yaml`, `source_xyz.yaml` with `from_header: to_field` pairs and basic transforms (strip `$`, cast int/float).

### 6) Run Registry & Manifest
- Mint `run_id` as `YYYYMMDD_HHMMSS_<shorthash>`
- Manifest must capture: inputs (with sha), outputs, config snapshot (`source`, `slate_id`, `mapping_name`), `schema_version` set, tags, notes.

---

## Non-Goals (this PRP)
- No optimizer/variant/field/sim execution.
- No full UI — a minimal CLI or script entrypoint is acceptable.
- No remote databases; keep DuckDB + Parquet on disk.

---

## Directory & Files (added/modified)

```
pipeline/
  ingest/
    __init__.py
    mappings/
      README.md
      example_source.yaml
    README.md
  registry/
    __init__.py
    README.md
  io/
    __init__.py
    README.md
data/
  reference/
  projections/
    raw/
    normalized/
  registry/
  runs/
docs/
  PRPs/
    PRP-1-ingest-normalization.md   ← this file (copy into repo if desired)
tests/
  test_ingest_normalize_smoke.py
  test_priority_latest_wins.py
  test_manifest_registry_write.py
```

> Stubs (`__init__.py`) can be empty; tests can be basic at first (see Test Plan). No heavy implementation required to pass PR — but enough to validate schemas + write Parquet with correct columns.

---

## Interfaces & I/O Contracts

### CLI (thin)
```
uv run python -m pipeline.ingest   --slate-id 20251101_NBA   --source primary   --projections path/to/projections.csv   --player-ids path/to/player_ids.csv   --mapping pipeline/ingest/mappings/example_source.yaml   --tag "PRP-1" --tag "demo"
```

**Outputs on success**
- Prints normalization preview (first 5 rows)
- Writes Parquet + manifest
- Appends Run Registry row with status=success

**Exit non-zero** on validation failure with a summary of errors.

### Parquet shapes
- Must validate exactly against PRP‑0 schemas (`Draft 2020-12`).

---

## Acceptance Criteria

1. **Schema compliance**  
   - `players.parquet`, `projections/raw`, `projections/normalized` validate against their schemas.  
   - `manifest.json` and `runs.parquet` validate against their schemas.

2. **Lineage integrity**  
   - `content_sha256` recorded in raw + normalized (lineage).  
   - `manifest.inputs[].content_sha256` matches computed hashes.

3. **Priority logic**  
   - Unit test proves: newer `updated_ts` rows replace older per `(slate_id, dk_player_id)`; tie-breaker honors `manual > primary > other`.

4. **Deterministic run IDs**  
   - `run_id` format enforced; surfaced in run folder names.

5. **Minimal UX**  
   - Preview prints and a clear success summary (paths, counts).

6. **CI green**  
   - Lints (ruff/black/yamllint) pass.  
   - JSON schema check job passes for all affected schemas.  
   - Tests pass on Python 3.11 (uv).

---

## Test Plan

- **Smoke**: upload tiny fixtures (3–5 players). Assert Parquet files exist & validate.  
- **Priority**: two uploads for same slate/player with different `updated_ts` + sources; assert “latest wins” and tiebreak.  
- **Lineage**: recompute file SHA and compare to stored values in raw/normalized/manifest.  
- **Manifest/Registry**: ensure run registered with correct paths + timestamps.  
- **Negative**: malformed salary or missing required column → validation error & non-zero exit.

Fixtures (add to `tests/fixtures/`):
- `player_ids.csv` (DK IDs + name/team/pos)
- `projections_sourceA.csv` (odd headers)
- `projections_sourceB.csv` (another header set)

---

## CI hooks (incremental)

- Reuse existing CI, ensure these jobs run on PRs touching `pipeline/ingest/**`, `pipeline/io/**`, `pipeline/registry/**`, and `tests/**`:
  - `ruff`, `black`, `mypy`, `pytest`, `yamllint` (schema/ingest configs)
  - JSON Schema syntax check (already in place)

---

## Risks & Mitigations
- **Header mismatch chaos** → Mapping catalog YAML + tests.  
- **Silent drift** → Manifest records full config + input hashes; Run Registry centralizes lookup.  
- **Schema churn** → Follow Schema Evolution policy (SemVer, optional-first).

---

## End Bookend — Merge & Tag

After approval & green CI:

```
PRP End → branch=feature/ingest-normalization
```

(Manual sequence)
```bash
# Merge PR
git checkout main
git merge --no-ff feature/ingest-normalization -m "PRP-1: Ingestion & Normalization + Run Registry"
git push origin main

# Tag baseline for this PRP
git tag -a v0.1.0 -m "PRP-1: Ingestion & Normalization + Run Registry"
git push origin v0.1.0
```

---

## Follow-ups (next PRPs)
- **PRP-2**: Optimizer Adapter (read normalized → write `optimizer_lineups` + `optimizer_metrics`, with manifest/registry).  
- **PRP-3**: Variant Catalog Adapter.  
- **PRP-4**: Field Sampler Adapter.  
- **PRP-5**: Simulator Adapter + Convergence Metrics.  
- **PRP-6**: Unified Dash (thin) wired to the adapters; “load previous run” from registry.
