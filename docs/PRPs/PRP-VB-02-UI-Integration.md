# PRP-VB-02 — Variant Builder UI Wiring (Controls + Results Grid)
**Date:** 2025-09-09  
**Owner:** Daniel S.  
**Repo:** `nba-dfs` (monorepo)  
**Branch Target:** `feature/vb-02-ui`

---

## 0) GitHub Actions (start → end)
**Start:**  
1) `git switch -c feature/vb-02-ui`  
2) `gh issue create -t "VB-02: UI wiring (controls + results grid)" -b "Wire UI to VB CLI/API; add grids, metrics, and run loading"`

**End:**  
1) `gh pr create -B main -t "VB-02: Variant Builder UI wiring" -b "Adds UI controls, results grid, diagnostics tiles, and run loader"`  


---

## 1) Purpose
Provide a clean, minimal UI for running Variant Builder and inspecting outputs **without** bloating VB core scope. This PRP mirrors the optimizer pattern: a thin UI that calls a CLI/API, renders Parquet artifacts, and preserves `run_id` as the single source of truth.

## 2) Scope (what's in / out)
**In (MVP UI):**
- Controls panel to invoke VB with typed params.
- Results grid for variants; diagnostics tiles.
- Run loader (select prior `run_id` and load artifacts).

**Out:** Advanced visualizations (ownership curves, annealing timelines), export-to-entries features (separate PRP).

## 3) UI Controls (map 1:1 to VBRequest)
- `run_id` (select from existing runs)  
- `num_variants` (int)  
- `seed` (int)  
- `per_base` (bool)  
- `min_uniques` (int)  
- `salary_min` / `salary_max` (int)  
- `locks` (chip-input of `player_id`)  
- `bans` (chip-input of `player_id`)  
- `exposure_caps` (table: `player_id` → cap %)  
- `team_limits` (table: `team` → max N)  
- `proj_noise_std` (float)  
- `max_dupe_rate` (float)

## 4) UX Flow
1. **Select Run** → loads `runs/{{run_id}}/optimizer/manifest.json` + sanity check.  
2. **Configure** → controls export a validated `VBRequest`.  
3. **Run VB** → call backend endpoint or spawn CLI job; show job status.  
4. **Render Results** on completion:  
   - `variants.parquet` in grid (see columns below)  
   - `diagnostics.parquet` summary tiles  
   - Persist last-used settings per `run_id`

## 5) Artifacts & Grids
**Variants Grid (server-paginated):**  
- Columns: `variant_id`, `base_lineup_id`, `slot1..slot8 (player_id)`, `salary_total`, `proj_sum`, `uniques_vs_base`, `ownership_penalty`  
- Toolbar: filter by `player_id`, `min_uniques`, salary range; export CSV (DK format optional in later PRP).

**Diagnostics Tiles:**  
- Jaccard (mean/median), `dupe_score` distribution (sparkline), rules violations count, runtime secs.  
- Link to raw `diagnostics.parquet`.

## 6) UI Implementation Notes
- **Components:**  
  - `/components/vb/VBControls.tsx`  
  - `/components/vb/VariantsGrid.tsx`  
  - `/components/vb/DiagnosticsBar.tsx`  
- **Page/Route:** `/vb` (or `/runs/[run_id]/vb`)  
- **State:** extend `useRunStore` (read-only run metadata + VB job status).  
- **Validation:** mirror Pydantic types in a shared `schemas.ts` (zod/yup) for UI.  
- **Job Runner:**  
  - Option A: REST `POST /api/vb/build` → job id → poll `GET /api/vb/status`  
  - Option B: spawn CLI (`uv run python -m vb.cli build ...`) via server route; stream logs.  
- **I/O:** UI never touches files directly; backend reads Parquet → returns paginated JSON.

## 7) Backend Endpoints (thin)
- `POST /api/vb/build` → body: `VBRequest` → starts job → `{ "job_id": "...", "run_id": "..." }`  
- `GET /api/vb/status?job_id=` → `{ "state": "queued|running|done|error", "message": "..." }`  
- `GET /api/vb/variants?run_id=&offset=&limit=&filters=` → page of variants  
- `GET /api/vb/diagnostics?run_id=` → summary metrics and sample rows

## 8) Tests
- **UI:** snapshot test for controls; table renders with mock data; filters work.  
- **API:** request validation; happy path e2e with a tiny fixture run; pagination bounds.  
- **Contract:** a golden `run_id` fixture under `/tests/fixtures/runs/demo_run/…`

## 9) Acceptance Criteria
- [ ] Can select an existing `run_id`, configure params, start a VB job, and view live status.  
- [ ] Variants grid loads from `variants.parquet` via backend, paginated, with filters.  
- [ ] Diagnostics tiles computed server-side from `diagnostics.parquet`.  
- [ ] `player_id` remains the single source of truth across UI, API, and artifacts.  
- [ ] No direct file access from the browser; all reads via backend endpoints.  
- [ ] All unit/integration tests pass in CI.

## 10) Risks & Mitigations
- **Scope creep:** keep advanced charts/export out of this PRP.  
- **State drift:** treat `run_id` as the key; never cache cross-run.  
- **Performance:** server pagination + column pruning for Parquet reads.

## 11) Follow-ups
- **PRP-VB-03:** Advanced diagnostics & dup estimator viz.  
- **PRP-VB-04:** DK-export and “Write to entries.csv”.  
- **PRP-VB-05:** Multi-contest view and blending.

---

### Dev Notes
- Keep “core vs UI” separation strict; UI should not compute lineup logic.  
- Prefer columnar reads with projection pushdown for grid endpoints.  
- Reuse the optimizer pattern: thin REST over CLI, immutable artifacts.
