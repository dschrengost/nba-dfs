# PRP-VB-UX-02 — Variant Builder Page

## 1. Goal
Deliver the Variant Builder page that mirrors the Optimizer layout while enabling users to generate, inspect, and manage lineup variants sourced from completed optimizer runs. The page must surface variant metrics, allow configuration of generation knobs, and integrate cleanly with the run registry and downstream field-sampler pipeline.

---

## 2. UX Layout

1. **Page Container & States**
   - Reuse the `PageContainer` scaffold used by the Optimizer page so the Variant page inherits grid-state handling (`empty → loading → loaded`).
   - Default state: `empty` (no run yet).
   - On "Run Variants" click → `loading` (skeleton grid) → `loaded` (lineup views).

2. **Configuration Panel**
   - **Source Selection**: dropdown listing recent optimizer runs via `/api/runs?module=optimizer`.
   - **Variant Settings**: expose core knobs from `configs/variants.yaml`:
     - `num_variants`, `swap_window.salary_delta/proj_delta`, `randomness`, `exposure_targets.player_caps/team_caps/position_caps`, `group_rules`, `uniques`, `avoid_dups`, `ownership_guidance.enabled/target`, `seed`.
   - Group basic vs. advanced settings; follow Optimizer audit recommendations for shadcn controls (sliders, tooltips).

3. **Run Controls & Summary**
   - Primary "Run Variants" button, secondary "Reset".
   - Summary bar after completion showing:
     - run_id, variant_count, aggregate metrics (entropy, chalk_index).
     - link to underlying optimizer run.

4. **Lineup Views**
   - Reuse `LineupViews` so cards/table tabs match optimizer experience.
   - Table columns (extending existing layout): lineup_id, score/proj, salary_used, own_avg, num_uniques_in_pool, parent_lineup_id, hamming_vs_parent, salary_delta, proj_delta, players by DK slot.
   - Variant table capped at 1,500 rows; existing table virtualization handles this size—no additional pagination required.
   - For cards, highlight deltas vs. parent (color-coded).

5. **Comparison Tools (phase 2)**
   - Toggle to overlay parent lineup vs. variant in card view.
   - Pre-compute core diff metrics (hamming distance, salary/projection deltas, number of uniques) during variant generation and store them in `variant_catalog.parquet`.
   - Lazy-load full parent lineup when the user requests a comparison to keep initial page load light.

---

## 3. Backend & Data Wiring

1. **POST `/api/variants`**
   - Accept: `{ slateId, fromRun?, config }`.
   - Spawn `uv run python -m processes.variants --slate-id <id> --from-run <run_id> --config-kv ...` mirroring optimizer API style.
   - Response: `{ ok, runId, variant_count, catalog_path, metrics_path, manifest_path }`.

2. **GET `/api/runs` & `/api/runs/<slate>/<module>/<run_id>`**
   - Already lists runs and fetches artifacts; extend route to recognize `module=variants` and serve `variant_catalog.parquet` + `metrics.parquet` instead of `lineups.json`.
   - Transform catalog to `lineups` array with slot/name/team/pos using player pool so `LineupViews` can compute salary/ownership.

3. **Run Registry Integration**
   - Variant adapter already writes `runs/<slate>/variants/<run_id>` with `variant_catalog.parquet`, `metrics.parquet`, `manifest.json`, and appends to `registry/runs.parquet`.
   - API should surface `run.meta` + aggregated metrics.

4. **Player Metadata & Metrics**
   - Provide `playerMap` in summary payload (names, teams, positions) so `useRosterMap` resolves IDs.
   - Recompute per-lineup projections and ownership inside the variant adapter using the optimizer’s formulas, ensuring new variants have accurate metrics even if the source optimizer run drifts.

---

## 4. Error States

| Scenario | UX Response | Mitigation |
|----------|-------------|------------|
| Missing optimizer run selection | Disable run button, inline message “Select base optimizer run” |
| Variant process exit ≠ 0 | Surface toast with stderr, keep page in previous state |
| Invalid config keys | Adapter warns on unknown keys (stdout); show warning banner |
| Catalog generation yields zero variants | Show info toast + empty grid |
| API timeouts / fetch errors | Display retry option and log to console |

---

## 5. Integration & Pipeline Considerations

1. **Unified Data Pipeline**
   - Variant Builder is step 2 in pipeline after data intake and before field sampling/injection.
   - Output contract aligns with PRP-VB-01 v2 spec: `variant_catalog` rows with lineup, salary_total, teams, provenance fields; validated via shared `LineupValidator`.

2. **Metrics Surface**
   - Aggregate metrics (entropy, chalk_index) included for downstream field sampler and dashboard summaries.
   - Per-lineup deltas enable leverage/duplication analysis before injection.

3. **Potential Gaps**
   - `runs/[slate]/[module]/[run_id]` route assumes `lineups.json`; must branch for variant artifacts.
   - Variant catalog lacks per-slot player metadata; API must join with `projections.csv` or optimizer pool to enrich lineups for UI.
   - `LineupViews` expects `score` and ownership; ensure adapter computes or derives these from player pool before sending to UI.
   - No existing endpoint to fetch player pool; consider `/api/pool?slate=<id>` if enrichment cannot rely on summary data.

4. **Validator & Schema**
   - Ensure `validators/lineup_rules.py` remains single source so Variant Builder, Field Sampler, and Simulator share constraints.

---

## 6. Acceptance Criteria

- User can select an optimizer run, configure variant settings, execute, and view variants in cards/table.
- API returns run metadata and lineup data conforming to `LineupTableData` schema.
- `variant_catalog.parquet` & `metrics.parquet` registered and retrievable via `/api/runs`.
- Per-lineup projections/ownership and diff metrics are computed during variant generation and exposed to the UI.
- Variant table capped at 1,500 rows and renders without performance issues.
- Error conditions handled with clear user feedback.
- Output artifacts ready for injection step per pipeline spec.

---

## 7. Open Questions

1. How will comparison tools visualize parent vs. variant efficiently for large runs?
2. Do we need pagination or virtualization thresholds beyond the current 1,500-row limit?

---

## 8. References

- Optimizer & Variant page components
- Variant run contract and metrics
- Variant configuration knobs
- Lineup table metrics blueprint
- Lineup transformation logic
- Pipeline overview and VB spec

