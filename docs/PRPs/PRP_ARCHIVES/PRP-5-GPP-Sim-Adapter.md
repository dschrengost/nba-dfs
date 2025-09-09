
# PRP-5: GPP Simulator Adapter (field + contest → sim_results + sim_metrics)

## Status
**Planned** — follows PRP-4 (Field Sampler). Can run in parallel with PRP-4 via worktrees.

## Objective
Create a **headless adapter + CLI** that runs a GPP tournament simulation using:
- Seeded **field lineups** (from PRP-4 `field.parquet`) and/or **variant catalog**,
- A **contest structure** (payouts, size, min cash, rake, etc.),
and produces schema-valid **`sim_results`** and **`sim_metrics`** artifacts plus **manifest/registry** entries.

No UI changes. Reuse the existing open-source simulator core; this PRP is adapter plumbing, validation, and discovery.

---

## Start Bookend — Branch
```
PRP Start → branch=feature/gpp-sim-adapter
```

---

## Scope & Deliverables

### 1) Adapter module
```
processes/gpp_sim/
  __init__.py
  __main__.py          # thin CLI
  adapter.py           # headless glue
  README.md
```
**Responsibilities**
- **Discovery:** resolve inputs in order of precedence
  - Field:
    1) `--field path/to/field.parquet`
    2) `--from-field-run <run_id>` → `<out_root>/runs/field/<run_id>/artifacts/field.parquet`
    3) (Optional) build from `variant_catalog.parquet` if `--field` not provided and `--variants` given
  - Contest structure:
    1) `--contest path/to/contest_structure.csv|parquet|json`
    2) `--from-contest path/to/dir` (search common names)
- **Config → knobs:** map config + `--config-kv` to simulator knobs
- **Invoke implementation:** dynamic load via `GPP_SIM_IMPL=module:function`
- **Outputs:**
  - `<out_root>/runs/sim/<run_id>/artifacts/sim_results.parquet` (schema: `sim_results`)
  - `<out_root>/runs/sim/<run_id>/artifacts/metrics.parquet` (schema: `sim_metrics`)
  - `<out_root>/runs/sim/<run_id>/manifest.json` (`run_type="sim"`)
- **Run Registry:** append a row with `primary_outputs` → `sim_results.parquet`

### 2) CLI
```
uv run python -m processes.gpp_sim   --slate-id 20251101_NBA   --config configs/sim.yaml   --seed 42   --out-root data   --tag PRP-5   [--field path/to/field.parquet]   [--from-field-run <field_run_id>]   [--variants path/to/variant_catalog.parquet]   [--contest path/to/contest_structure.csv|parquet|json]   [--schemas-root path/to/pipeline/schemas]   [--validate/--no-validate]   [--verbose]
```

### 3) Config → knobs (initial set)
- `num_trials`: Monte Carlo trials / simulations
- `projection_model`: which columns to use (mean/ceil/floor) for scoring
- `boom_bust`: stochastic volatility model parameters
- `dup_penalty`: de-duplication treatment in payouts (if modeling unique entries)
- `late_swap`: whether to allow late swap modeling (stub/no-op initially)
- `min_cash_prob`: option to report probability of min cash / ROI
- `seed`: RNG seed
- Extra keys preserved under `extras`

### 4) Validation
- **Fail-fast**: validate each `sim_results` and `sim_metrics` row against schemas **before** any writes
- Guard inputs:
  - Field rows have 8 players and ≤ 50k salary (if available)
  - Contest structure is contiguous, sums match entries/payouts (document cross-checks)
- Manifest + registry validation via schemas
- Deterministic `run_id = YYYYMMDD_HHMMSS_<shorthash>` over input SHA(s) + resolved config + seed

### 5) Metrics (initial)
- ROI distribution by lineup and summary aggregates
- Cash rate / top-1% rate estimates
- EV per lineup and per-seed variance
- Contest-level summaries (overlay, rake implied etc.)

### 6) Outputs & DK export
- `sim_results.parquet` — per-lineup simulated results (schema: `sim_results`)
- `metrics.parquet` — aggregates (schema: `sim_metrics`)
- **Export:** optional `--export-dk-csv path.csv` that writes a DK-compliant CSV from selected top lineups
  - Uses `export_csv_row` from upstream artifacts
  - Writes **DK uploadable** structure only when explicitly requested

### 7) Tests
- `tests/test_sim_adapter_smoke.py` — end-to-end with tiny field + tiny contest
- `tests/test_sim_failfast_no_write.py` — invalid field or contest blocks writes
- `tests/test_sim_run_id_determinism.py` — same inputs/config → same run_id; seed change alters it
- `tests/test_sim_manifest_registry.py` — manifest/registry validations
- `tests/test_sim_metrics_shapes.py` — metrics schema and expected keys
- `tests/test_sim_verbose_and_schemas_root.py` — robust schema path + verbose breadcrumb

### 8) Example config + contest
- `configs/sim.yaml` with commented defaults
- `tests/fixtures/contest_structure.csv` — tiny valid contest (e.g., 20 entries, top-5 payout)

---

## Inputs & Outputs

### Inputs
- **Field** from PRP-4 (`field.parquet`), or variants as fallback
- **Contest structure** `contest_structure.csv|parquet|json` (schema: `contest_structure`)

### Outputs
- `sim_results.parquet` (schema: `sim_results`)
- `metrics.parquet` (schema: `sim_metrics`)
- `manifest.json` (`run_type="sim"`)
- Registry append

---

## Acceptance Criteria
- Adapter is **headless** and produces schema-valid `sim_results` and `sim_metrics`
- Deterministic `run_id` and manifest/registry integration
- `--validate` on by default; `--schemas-root` robust
- No Streamlit/UI imports
- All tests pass locally and in CI
- README documents discovery policy, config knobs, export behavior

---

## Risks & Mitigations
- **Performance**: simulation can be heavy — begin with small trial counts; consider chunked writes later
- **Contest validation**: cross-field checks not expressible in JSON Schema — document and implement in adapter
- **Input variability**: protect against missing columns or invalid DK rows

---

## Directory Changes
```
processes/gpp_sim/
  __init__.py
  __main__.py
  adapter.py
  README.md
configs/
  sim.yaml
tests/
  fixtures/contest_structure.csv
  test_sim_adapter_smoke.py
  test_sim_failfast_no_write.py
  test_sim_run_id_determinism.py
  test_sim_manifest_registry.py
  test_sim_metrics_shapes.py
  test_sim_verbose_and_schemas_root.py
```

---

## CI Hooks
Add/extend a workflow to include GPP sim paths:
```yaml
on:
  pull_request:
    paths:
      - "processes/gpp_sim/**"
      - "pipeline/schemas/**"
      - "configs/sim.yaml"
      - "tests/test_sim_*py"
```
Run: ruff, black, mypy (scoped), pytest (focused), CLI `--help`.

---

## End Bookend — Merge & Tag
```
PRP End → branch=feature/gpp-sim-adapter
```
(Manual)
```bash
git checkout main
git merge --no-ff feature/gpp-sim-adapter -m "PRP-5: GPP simulator adapter"
git push origin main
git tag -a v0.6.0 -m "PRP-5: GPP simulator adapter"
git push origin v0.6.0
```
