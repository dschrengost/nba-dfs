# PRP-4: Field Sampler Adapter (variant_catalog → field + metrics)

## Status
**Planned** — follows PRP-3/3a. Parallelizable with optimizer/variants work.

## Objective
Provide a **headless adapter + CLI** that samples a representative contest field from the **variant catalog** (and/or base optimizer lineups), producing schema-valid `field` and `field_metrics`, plus manifest/registry entries. No UI. No core sampling algorithm changes — adapter plumbing, validation, and discovery only.

---

## Start Bookend — Branch
```
PRP Start → branch=feature/field-sampler-adapter
```

---

## Scope & Deliverables

### 1) Adapter module
```
processes/field_sampler/
  __init__.py
  __main__.py          # thin CLI
  adapter.py           # headless glue
  README.md
```
**Responsibilities**
- **Discovery (inputs):** resolve input catalog(s) in order of precedence:
  1) `--input` explicit `variant_catalog.parquet`
  2) `--from-run <variants_run_id>` → `<out_root>/runs/variants/<run_id>/artifacts/variant_catalog.parquet`
  3) Latest `run_type="variants"` in registry for `slate_id` (use `primary_outputs[0]` or construct canonical path)
  4) (Optional) allow merging multiple catalogs with `--inputs` for large fields
- **Config → knobs:** map config + `--config-kv` to sampler knobs
- **Invoke implementation:** dynamic load via `FIELD_SAMPLER_IMPL=module:function`
- **Outputs:**
  - `<out_root>/runs/field/<run_id>/artifacts/field.parquet` (schema: `field`)
  - `<out_root>/runs/field/<run_id>/artifacts/metrics.parquet` (schema: `field_metrics`)
  - `<out_root>/runs/field/<run_id>/manifest.json` (`run_type="field"`)
- **Run Registry:** append a row with `primary_outputs` → `field.parquet`

### 2) CLI
```
uv run python -m processes.field_sampler   --slate-id 20251101_NBA   --config configs/field.yaml   --seed 42   --out-root data   --tag PRP-4   [--input path/to/variant_catalog.parquet]   [--inputs path1 path2 ...]   [--from-run <variants_run_id>]   [--schemas-root path/to/pipeline/schemas]   [--validate/--no-validate]   [--verbose]
```

### 3) Config → knobs (initial set)
- `field_size`: total number of sampled lineups (e.g., contest size)
- `source_mix`: weights for sources (e.g., base optimizer vs variants if supported)
- `sampling_mode`: one of `["iid", "weight_by_proj", "weight_by_own", "stratified"]`
- `ownership_curve`: optional distribution to target (e.g., contest-wide chalkiness)
- `diversity`: target uniqueness or Jaccard thresholds between neighbors
- `team_limits`: max from team, stack constraints (soft/hard)
- `de-dup`: remove exact duplicates by sorted player set
- `seed`: RNG seed
- Extra keys preserved under `extras`

### 4) Validation
- **Fail-fast**: validate each `field` and `field_metrics` row against schemas **before** any writes
- Lineup sanity: 8 players, DK slot coverage (if present), salary cap ≤ 50000
- Manifest + registry validation via schemas
- Deterministic `run_id = YYYYMMDD_HHMMSS_<shorthash>` over input SHA(s) + resolved config + seed

### 5) Metrics (initial)
- `exposure`: per-player frequency
- `team_exposure`: per-team frequency
- `pairwise_jaccard`: summary stats (mean/max) over field
- `chalk_index`: max player exposure
- `entropy`: diversity proxy (same as variants, adapted to field size)

### 6) Tests
- `tests/test_field_adapter_smoke.py` — end-to-end with tiny variant catalog + stub sampler
- `tests/test_field_failfast_no_write.py` — 7-player or >50k lineup blocks writes
- `tests/test_field_run_id_determinism.py` — same inputs/config → same run_id; seed change alters it
- `tests/test_field_manifest_registry.py` — manifest/registry validations
- `tests/test_field_dedup_and_diversity.py` — de-dup works; diversity metric improves with higher `diversity`
- `tests/test_field_verbose_and_schemas_root.py` — robust schema path + verbose breadcrumb

### 7) Example config
- `configs/field.yaml` with commented defaults

---

## Inputs & Outputs

### Inputs
- **Primary:** `variant_catalog.parquet` (schema: `variant_catalog`), resolved by `--input`, `--from-run`, or registry
- **Optional:** multiple catalogs (`--inputs`) to assemble larger fields

### Outputs
- `field.parquet` (schema: `field`)
- `metrics.parquet` (schema: `field_metrics`)
- `manifest.json` (`run_type="field"`)
- Registry append

---

## Acceptance Criteria
- Adapter is **headless** and produces schema-valid `field` and `field_metrics` artifacts
- Deterministic `run_id` matches PRP-2/3 style
- `--validate` default on; `--schemas-root` robust (repo-relative default)
- No Streamlit/UI imports
- All tests pass locally and in CI
- README documents discovery policy, config knobs, and preview vs export distinctions

---

## Risks & Mitigations
- **Sampling performance** → start with simple stub; chunked writes if needed (optional follow-up)
- **Schema drift** → validate rows pre-write; rely on PRP-0 schemas
- **Input variability** → guard for missing columns; produce clear errors

---

## Directory Changes
```
processes/field_sampler/
  __init__.py
  __main__.py
  adapter.py
  README.md
configs/
  field.yaml
tests/
  test_field_adapter_smoke.py
  test_field_failfast_no_write.py
  test_field_run_id_determinism.py
  test_field_manifest_registry.py
  test_field_dedup_and_diversity.py
  test_field_verbose_and_schemas_root.py
```

---

## CI Hooks
Extend a workflow to include field-sampler paths:
```yaml
on:
  pull_request:
    paths:
      - "processes/field_sampler/**"
      - "pipeline/schemas/**"
      - "configs/field.yaml"
      - "tests/test_field_*py"
```
Run: ruff, black, mypy (scoped), pytest (focused), CLI `--help`.

---

## End Bookend — Merge & Tag
```
PRP End → branch=feature/field-sampler-adapter
```
(Manual)
```bash
git checkout main
git merge --no-ff feature/field-sampler-adapter -m "PRP-4: Field sampler adapter"
git push origin main
git tag -a v0.5.0 -m "PRP-4: Field sampler adapter"
git push origin v0.5.0
```
