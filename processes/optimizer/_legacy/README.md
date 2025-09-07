# Legacy Optimizer — Inventory and De‑UI Plan (PRP‑2L)

## Purpose
Document the legacy optimizer UI module set, identify reusable compute surfaces, and mark UI touch‑points for later extraction. No behavior changes here.

## Files and Roles
- `optimize.py` (UI shell)
  - Streamlit app: page config, controls, AG Grid display, exports, run comparison, retention utilities.
  - Bridges projections → `nba_optimizer_functional.optimize_with_diagnostics` and optional DK‑strict flows.
  - Manages session state, spinners, and download buttons.
- `nba_optimizer_functional.py` (compute core)
  - Functional API wrapping CBC/CP‑SAT solvers, constraints application, ownership penalty models, DK‑ID attachment.
  - Public entrypoints: `optimize`, `optimize_with_diagnostics`, `optimize_dk_strict`, `optimize_to_dk_csv`, `optimize_dk_strict_to_csv`.
  - Helpers: validation (`validate_projections`), ID attachment (`attach_player_ids_if_available`), data shaping (`convert_projections_to_players`), solver problem builder (`build_problem`).
- `cpsat_solver.py` (solver helpers)
  - Ownership penalty curve helpers, input contract checks, objective telemetry for CP‑SAT path.
  - No UI dependencies.
- `pruning.py` (candidate reduction)
  - Safe pruning of candidate sets prior to solve.
  - No UI dependencies.

## Stable Symbols for Reuse (API candidates)
- `nba_optimizer_functional.optimize_with_diagnostics(projections_df, constraints, seed, site, player_ids_df=None, engine="cbc") -> (lineups: List[Lineup], diagnostics: Dict)`
- `nba_optimizer_functional.optimize(projections_df, constraints, seed, site, player_ids_df=None, engine="cbc") -> List[Lineup]`
- `nba_optimizer_functional.optimize_dk_strict(projections_path, constraints, seed, player_ids_path=None, engine="cbc") -> (lineups, diagnostics)`
- `nba_optimizer_functional.optimize_to_dk_csv(projections_df, constraints, seed, player_ids_df=None) -> str`
- `nba_optimizer_functional.optimize_dk_strict_to_csv(projections_path, constraints, seed, player_ids_path=None, engine="cbc") -> str`
- `nba_optimizer_functional.validate_projections(df, site) -> None`
- `nba_optimizer_functional.attach_player_ids_if_available(df, site, ids_df) -> (df, diag)`
- `nba_optimizer_functional.convert_projections_to_players(df, proj_min) -> List[Dict]`
- `nba_optimizer_functional.build_problem(players, constraints, site, override_coeffs=None) -> (problem, var_index, lp_vars, base_obj)`

These provide a usable compute surface for a headless adapter.

## Data Contracts (summary)
Inputs (projections_df expected columns)
- Required: `name` (str), `team` (str, uppercase 2–4), `position` (str like `PG` or `PG/SG`), `salary` (int), `proj_fp` (float)
- Optional: `own_proj` (float in [0,1] or percent), `stddev` (float), `minutes` (float), `dk_id` (str|int)

Outputs
- Lineups: `List[Lineup]` (structs: players with `player_id`, `name`, `team`, `positions`, `salary`, `proj`, `own_proj?`, `dk_id?`)
- Diagnostics: `{success_rate, warnings, errors, normalization: {ownership{...}}, ownership_penalty{...}, engine, …}`
- CSV helpers return DK importable CSV (header `PG,SG,SF,PF,C,G,F,UTIL`).

## Known UI Dependencies and Side Effects
- `optimize.py` uses `streamlit` and `st_aggrid`; contains large AG Grid CSS, `st.sidebar`, `st.download_button`, `st.session_state` mutations, and file export helpers.
- Path hack: `sys.path.append(os.path.join(__file__, '../../'))` to import `backend.*`.
- UI‑only exports for CSV previews and run retention tooling.

## De‑UI Extraction Plan (summary)
Target headless API (for PRP‑2 adapter):
- `run_optimizer(projections_df, constraints: dict, seed: int, site: str, engine: str) -> (lineups_df, metrics_dict)`
  - Map to: `optimize_with_diagnostics` + `lineups_to_grid_df` for tabular form.
  - Diagnostics passed through; ownership penalty telemetry included when present.
Minimal refactors in PRP‑2
- Move/export helpers `build_optimizer_grid_options`, `export_optimizer_results`, AG Grid CSS → UI package; not needed headless.
- Remove `sys.path` hacks; import via proper package path.
- Replace `st.cache_*` with local memoization (if needed) or remove.
- Isolate file I/O (CSV export, retention) behind adapter functions.

## UI Touchpoints Tagged
- Streamlit imports and session state usage in `optimize.py`.
- AG Grid imports and CSS in `optimize.py`.
- Path hack in `optimize.py`.
- Download buttons and export helpers in `optimize.py`.

No runtime behavior changed.

