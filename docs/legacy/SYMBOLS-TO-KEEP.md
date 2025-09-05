# Symbols to Keep — Stable API (PRP‑2L)

The following symbols provide a stable, headless surface for the optimizer adapter. Signatures reflect current code; data contracts summarized inline.

- `optimize_with_diagnostics(projections_df, constraints, seed, site, player_ids_df=None, engine="cbc") -> (lineups, diagnostics)`
  - From: `processes/optimizer/_legacy/nba_optimizer_functional.py`
  - Inputs: `projections_df` with columns: name, team, position, salary, proj_fp, [own_proj?, stddev?, minutes?, dk_id?]
  - Outputs: `lineups` (List[Lineup]), `diagnostics` dict with dk‑id match stats, ownership normalization, and engine info.

- `optimize(projections_df, constraints, seed, site, player_ids_df=None, engine="cbc") -> List[Lineup]`
  - Convenience wrapper returning only lineups.

- `optimize_dk_strict(projections_path, constraints, seed, player_ids_path=None, engine="cbc") -> (lineups, diagnostics)`
  - Enforces DK‑strict contracts (real DK IDs only) using `dk_data/` loaders.

- `optimize_to_dk_csv(projections_df, constraints, seed, player_ids_df=None) -> str`
  - Runs optimizer and returns a DK import CSV string.

- `optimize_dk_strict_to_csv(projections_path, constraints, seed, player_ids_path=None, engine="cbc") -> str`
  - DK‑strict end‑to‑end flow to CSV.

- `validate_projections(df, site) -> None`
  - Ensures required columns present; raises `OptimizerError` on failure.

- `attach_player_ids_if_available(df, site, ids_df) -> (df, diag)`
  - Attaches DK IDs from provided DataFrame or defaults; returns diagnostics including success rate.

- `convert_projections_to_players(df, proj_min) -> List[Dict]`
  - Maps projections to solver player dicts: `{player_id, name, team, positions[], salary, proj, own_proj?, dk_id?}`.

- `build_problem(players, constraints, site, override_coeffs=None) -> (problem, var_index, lp_vars, base_obj)`
  - Constructs solver problem with deterministic variable ordering and returns the base objective expression.

Usage note: The adapter for PRP‑2 should not import Streamlit or AG Grid; use only these symbols to run solves and obtain diagnostics. Lineups can be converted to a tabular DataFrame with `lineups_to_grid_df` (from legacy DK helpers) if needed for downstream parity.

