
# PRP-2 (Tailored): Optimizer Adapter using existing `optimize.py`

## Objective
Reuse your prior optimizer (CP-SAT/ownership-penalty knobs) by wrapping **`optimize.py`** behind a thin adapter that:
- Consumes **normalized projections** (PRP‑0 schema),
- Translates config → constraints,
- Calls the existing `run_optimizer(...)` path,
- Emits schema‑valid `optimizer_lineups.parquet`, `optimizer_metrics.parquet`, and a manifest + registry row,
- Stays *headless* (no Streamlit UI coupling).

---

## Start Bookend — Branch
```
PRP Start → branch=feature/optimizer-adapter
```

---

## What we have (from your `optimize.py` inspection)
- Public entrypoint: `run_optimizer(projections_df, constraints_dict, seed, site, engine="cbc")`
- Export utilities: `export_dk_csv(valid_df)`, `transform_lineups_for_grid(lineups, site, view_mode="compact")`
- Telemetry/export helpers: `export_with_telemetry(valid_df, projections_df)`, `persist_run_to_history(...)`
- Display utilities (Streamlit): *to be ignored for adapter*
- Imports reference `backend.nba_optimizer_functional.optimize_with_diagnostics` and `backend.types.Constraints`

**Implication**: The adapter should **not** import Streamlit; it should import only the functional core used by `run_optimizer`. If those `backend.*` modules are not present in this repo, we’ll provide a **shim** or rename imports to your local paths.

---

## Scope & Deliverables

### 1) Adapter module (headless)
```
processes/optimizer/
  adapter.py      # core glue: read → map → run → write
  __main__.py     # thin CLI wrapper
  README.md       # usage & config knobs
```

**Responsibilities:**
- Read `data/projections/normalized/*` for a given `slate_id`.
- Build `constraints_dict` from a user `config` (YAML/JSON).
- Call `run_optimizer(projections_df, constraints_dict, seed, site, engine)`.
- Convert outputs → `optimizer_lineups.schema.yaml` & `optimizer_metrics.schema.yaml`.
- Compute `export_csv_row` (DK header order defined in schemas README).
- Write Parquet + `manifest.json` (run_type="optimizer") and append Run Registry.
- No Streamlit calls, no UI side effects.

### 2) CLI wrapper
```
uv run python -m processes.optimizer   --slate-id 20251101_NBA   --site DK   --config configs/optimizer.yaml   --engine cbc   --seed 42   --out-root data   --tag PRP-2
```
- `--config` may be YAML/JSON; support inline `--config-kv key=val` pairs as a bonus.

### 3) Config → constraints mapping (initial set)
Map these knobs into `constraints_dict` / `Constraints`:
- `num_lineups`, `max_salary (≤50000)`, `min_salary` (optional)
- `lock` / `ban` (lists of `dk_player_id`)
- `exposure_caps` per player/team/position
- `stacking` / `group_rules` (if your previous build used `GroupRule`)
- `ownership_penalty` `{enabled, mode, lambda}` (your prior knob)
- `uniques`, `max_from_team`, `min_from_team`, `position_rules`
- `randomness` (if supported by solver)
- Any additional toggles your `run_optimizer` consumes

Document unsupported keys as **ignored with warning** (for now).

### 4) Outputs
- `data/runs/optimizer/<run_id>/lineups.parquet` (schema: `optimizer_lineups`)
- `data/runs/optimizer/<run_id>/metrics.parquet` (schema: `optimizer_metrics`)
- `data/runs/optimizer/<run_id>/manifest.json` (run_type="optimizer", schema_version current)
- Append to `data/registry/runs.parquet`

### 5) Tests
- `tests/test_optimizer_adapter_smoke.py` — feed tiny normalized projections; use a **mock** `run_optimizer` return to keep tests fast.
- `tests/test_optimizer_export_dk_csv.py` — verify `export_csv_row` header/order.
- `tests/test_optimizer_ownership_penalty_flag.py` — ensure knob passes through to constraints.
- `tests/test_optimizer_manifest_registry.py` — manifest/registry assertions.

> Note: If `backend.*` modules aren’t available, tests will inject a small stub to simulate `run_optimizer` outputs.

---

## Integration details

### Inputs (read path)
- Pick the **latest** normalized file for `slate_id` by `updated_ts` per `(slate_id, dk_player_id)` (this is already handled in ingestion; adapter reads the table produced).

### Transform to solver
- Build the solver’s expected `projections_df` from normalized projections:
  - Must include `dk_player_id`, `pos`, `salary`, `proj_fp` (and optionally `ceil_fp`, `floor_fp`, `own_proj`).

- Build `constraints_dict` consistent with previous project:
  - If your old code used a dataclass `Constraints`, the adapter can construct it from the dict.

### From solver → schema
- Lineups: list of players (8) → `players` (list of `dk_player_id`), `total_salary`, `proj_fp`, etc.
- DK export: build `export_csv_row` in canonical order defined in schemas README.
- Metrics: collect aggregates (mean/median proj, salary utilization) + any solver telemetry. Keep extras inside a nested `extras` object to remain schema‑strict.

### Manifest
- `run_type="optimizer"`
- `inputs`: references to normalized projections + config (with `content_sha256`)
- `outputs`: paths to lineups/metrics
- `config`: full resolved config
- `tags`, `schema_version`, `created_ts`

---

## Acceptance Criteria
- Adapter runs headless, no Streamlit dependencies.
- Writes schema‑valid `lineups.parquet`, `metrics.parquet`, and manifest.
- Registry append succeeds; `primary_outputs` points to `lineups.parquet`.
- Ownership penalty knob passes through to constraints and is visible in metrics/telemetry.
- CI green with new tests.

---

## Risks & Mitigations
- **Missing `backend.*` modules** → Provide shims or adjust imports to the local module path; tests use mocks.
- **I/O mismatch** → Strict schema validation + small golden fixtures to catch early.
- **Export shape drift** → One test explicitly checks DK header/order.

---

## End Bookend — Merge & Tag
```
PRP End → branch=feature/optimizer-adapter
```

(Manual)
```bash
git checkout main
git merge --no-ff feature/optimizer-adapter -m "PRP-2: Optimizer adapter using existing optimize.py"
git push origin main
git tag -a v0.3.0 -m "PRP-2: Optimizer adapter"
git push origin v0.3.0
```
