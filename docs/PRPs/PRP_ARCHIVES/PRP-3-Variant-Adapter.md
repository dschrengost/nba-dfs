
# PRP-3: Variant Adapter (lineups → variant_catalog + metrics)

## Status
**Planned** — next after PRP-2 (Optimizer Adapter), PRP-1c (Ingest Docs), and PRP-2L (Legacy Docs/De-UI).

## Objective
Wrap the existing **variant builder** logic behind a headless adapter that:
- Consumes **optimizer lineups** (schema: `optimizer_lineups`),
- Applies variant configuration (exposure shaping, groups, swaps, randomization),
- Produces a **variant catalog** and **variant metrics** conforming to PRP-0 schemas,
- Emits a **manifest** + **Run Registry** row.

No UI; no changes to core variant algorithms, only adapter plumbing + validation.

---

## Start Bookend — Branch
```
PRP Start → branch=feature/variant-adapter
```

---

## Scope & Deliverables

### 1) Adapter module
```
processes/variants/
  __init__.py
  __main__.py            # thin CLI
  adapter.py             # headless glue
  README.md
```
**Responsibilities**
- Read **optimizer lineups** for a given `slate_id`:
  - Prefer manifest-driven discovery (latest optimizer run for slate) OR `--input` path override.
- Load `config` (YAML/JSON or inline `--config-kv`), map to variant knobs.
- Invoke legacy variant builder function (`OPTIMIZER_VARIANT_IMPL=module:function` env override supported).
- Write:
  - `data/runs/variants/<run_id>/variant_catalog.parquet` (schema: `variant_catalog`)
  - `data/runs/variants/<run_id>/metrics.parquet` (schema: `variant_metrics`)
  - `data/runs/variants/<run_id>/manifest.json` (`run_type="variants"`)
- Append **Run Registry** row with `primary_outputs` → `variant_catalog.parquet`.

### 2) CLI
```
uv run python -m processes.variants   --slate-id 20251101_NBA   --config configs/variants.yaml   --seed 42   --out-root data   --tag PRP-3   [--input path/to/optimizer_lineups.parquet]   [--schemas-root path/to/pipeline/schemas]   [--validate/--no-validate]   [--verbose]
```
- Optional: `--from-run <optimizer_run_id>` to resolve input via manifest/registry.

### 3) Config → knobs (initial set)
- `num_variants`: int total or per-base-lineup multiplier
- `swap_window`: (min,max) salary deltas or projection deltas
- `randomness`: float (0–1) perturbation on projections or selection
- `exposure_targets`: per-player/team/position caps
- `group_rules`: soft/hard groupings you want kept/avoided
- `uniques`: min changes from base lineup
- `avoid_dups`: true/false (deduplicate variants by sorted player set)
- `ownership_guidance`: optional shaping similar to optimizer knob
- `seed`: RNG seed
- Extra keys preserved in `extras`

### 4) Validation
- **Fail-fast**: validate `variant_catalog` and `variant_metrics` rows against schemas **before** writes.
- Validate `manifest` and **runs registry** row via JSON Schema.
- Lineup sanity (each variant has 8 players, DK slots filled, ≤ 50k).

### 5) Manifests & Registry
- `run_type="variants"`
- Inputs include: optimizer lineups (with content_sha256), config (file + inline kv) hashes
- Deterministic `run_id = YYYYMMDD_HHMMSS_<shorthash>` derived from input SHA(s) + resolved config + seed.

### 6) Tests
- `tests/test_variants_adapter_smoke.py` — end-to-end with tiny fixture lineups + stub variant builder.
- `tests/test_variants_failfast_no_write.py` — invalid variant (7 players) blocks writes.
- `tests/test_variants_run_id_determinism.py` — same inputs/config → same `run_id`; seed change alters it.
- `tests/test_variants_manifest_registry.py` — manifest/registry validations.
- `tests/test_variants_exposure_caps.py` — caps honored (using stubbed variant builder).
- `tests/test_variants_verbose_and_schemas_root.py` — robust schema path + verbose prints.

### 7) Example config
- `configs/variants.yaml` with commented knobs and sensible defaults.

---

## Inputs & Outputs

### Input
- **Primary**: `optimizer_lineups.parquet` (schema: `optimizer_lineups`) resolved by:
  1) `--input` explicit path, or
  2) latest optimizer run for `slate_id` from registry/manifest.

### Outputs
- `variant_catalog.parquet` (schema: `variant_catalog`)
- `metrics.parquet` (schema: `variant_metrics`)
- `manifest.json` (`run_type="variants"`)
- Registry append

---

## Acceptance Criteria
- Adapter is **headless** and produces schema-valid artifacts.
- Deterministic `run_id` logic matches PRP-2 approach.
- `--validate` on by default; `--schemas-root` robust (repo-relative default).
- Adapter **does not** import Streamlit/UI packages.
- All tests pass locally and in CI.
- README documents CLI, discovery policy, preview vs export distinctions.

---

## Risks & Mitigations
- **Old variant builder imports UI** → use env override to point at a headless function (or stub in tests).
- **Schema drift** → validate rows pre-write; rely on PRP-0 schemas.
- **Performance** → variants can be large; write in chunks if needed (optional follow-up).

---

## Directory Changes
```
processes/variants/
  __init__.py
  __main__.py
  adapter.py
  README.md
configs/
  variants.yaml
tests/
  test_variants_adapter_smoke.py
  test_variants_failfast_no_write.py
  test_variants_run_id_determinism.py
  test_variants_manifest_registry.py
  test_variants_exposure_caps.py
  test_variants_verbose_and_schemas_root.py
```

---

## CI Hooks
Extend/clone the optimizer workflow to include variant paths:
```yaml
on:
  pull_request:
    paths:
      - "processes/variants/**"
      - "pipeline/schemas/**"
      - "configs/variants.yaml"
      - "tests/test_variants_*py"
```
Run: ruff, black, mypy (scoped), pytest (focused), CLI `--help`.

---

## End Bookend — Merge & Tag
```
PRP End → branch=feature/variant-adapter
```
(Manual)
```bash
git checkout main
git merge --no-ff feature/variant-adapter -m "PRP-3: Variant adapter"
git push origin main
git tag -a v0.4.0 -m "PRP-3: Variant adapter"
git push origin v0.4.0
```
