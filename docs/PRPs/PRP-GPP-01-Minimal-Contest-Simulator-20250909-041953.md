# PRP-GPP-01 — Minimal Contest Simulator (Vertical Slice)

## GitHub Actions (Start)
- **Create branch:** `git switch -c feat/prp-gpp-01-min-sim`
- **Sync main:** `git fetch origin && git pull --ff-only`
- **Set UV env:** ensure `uv` is installed (`pipx install uv` if needed).

---

## Objective
Stand up a thin end-to-end **GPP contest simulator** using the legacy engine at `processes/gpp_sim/_legacy/nba_gpp_simulator.py` as a reference, producing stable I/O contracts and run metrics. This closes the loop (Optimizer → Variant Builder → Field Sampler → **GPP Sim**) and validates the “single source of truth”.

## Scope (MVP)
- CLI entry: `processes/gpp_sim/__main__.py` with `uv run -m processes.gpp_sim`.
- Inputs:
  - `tournament_lineups.csv` (seeded with Sampled Field + Variant Catalog).
  - `contest_structure.csv` (buy-in, rake, payout table; support CSV or JSON).
  - Optional: `ownership.csv` for duplication/field realism (if present).
- Engine:
  - Deterministic scoring pass (use provided lineup projections/actuals as-is).
  - Exact-dup grouping: treat identical player sets as 1 lineup with N entries.
  - Payout application by finishing positions given `contest_structure`.
- Outputs:
  - `runs/<YYYYMMDD_HHMMSS>/sim_results.parquet`
  - `runs/<...>/summary.json` (ROI, ITM%, Net$, Top-1/5/10% hit rates, dup stats).
  - `runs/<...>/lineups_out.csv` (optional, DK-compliant for download/entries merge).
- UI hooks:
  - Return a `RunSummary` object compatible with existing `components/metrics/RunSummary.tsx` patterns.
  - Simple grid endpoint for lineup-level results (id, score, finish, prize, dup_count).

## Non-Goals (this PRP)
- Advanced field-strength models, stochastic outcome sampling, or correlation modeling.
- Ownership modeling improvements (placeholder only).
- Full dashboard integration (wire basic routes only).

---

## File & Data Contracts
- **`tournament_lineups.csv`**
  - Columns (required): `lineup_id`, `player_ids` (pipe- or comma-joined DK IDs), `entry_count` (default=1)
  - Optional: `proj_points`, `salary`, `ownership` (float 0-1 per lineup)
- **`contest_structure.csv`**
  - Columns: `place`, `payout` (absolute $) or use `total_entries`, `buy_in`, `rake`, and a `payout_table` JSON
- **Output `summary.json`**
  ```json
  {
    "entries": 150,
    "unique_lineups": 120,
    "total_prizes": 1234.50,
    "total_fees": 300.00,
    "net": 934.50,
    "roi": 3.115,
    "itm_pct": 0.227,
    "dup": { "mean": 1.4, "p95": 3, "max": 12 }
  }
  ```

---

## Implementation Plan
1. **Scaffold**
   - New pkg: `processes/gpp_sim/`
   - `__main__.py` for CLI: args for `--lineups`, `--contest`, `--outdir`, `--format parquet|csv`.
   - `engine.py` minimal: load inputs → score → rank → apply payouts → aggregate metrics.
   - `io_schemas.py`: pydantic dataclasses for strict validation (fail fast).
2. **Legacy Port**
   - Borrow stable helpers from `_legacy/nba_gpp_simulator.py` where sensible; keep `_legacy/` intact for diffing.
3. **Dup Handling**
   - Group by normalized player set string; expand by `entry_count`.
4. **Metrics**
   - ROI, ITM%, net $, dup stats; per-lineup prize/finish.
5. **Persistence**
   - All artifacts under `runs/<timestamp>/` with `meta.json` describing inputs.
6. **UI Wiring**
   - Emit `RunSummary`-compatible JSON; small Next.js API route stub if needed.

---

## UV Dependencies
- `pydantic>=2`
- `polars>=1` (or `pandas>=2`; prefer `polars` for speed)
- `pyarrow>=16`
- Add via UV: `uv add pydantic polars pyarrow`

---

## Tests
- `tests/test_gpp_sim_engine.py`
  - Loads tiny fixtures for lineups + contest; asserts ROI/ITM and dup grouping.
  - Contract tests for schema validation and missing columns.
- `tests/test_gpp_sim_cli.py`
  - Smoke test: runs CLI, asserts artifacts exist in `runs/<ts>/`.
- **Fixtures**: `tests/fixtures/gpp/{lineups.csv, contest.csv}`

---

## Acceptance Criteria
- `uv run -m processes.gpp_sim --lineups fixtures/lineups.csv --contest fixtures/contest.csv` produces:
  - `runs/<ts>/summary.json` with ROI/ITM/net & dup stats.
  - `runs/<ts>/sim_results.parquet` with ≥ these columns: `lineup_id, score, finish, prize, dup_count`.
- Run resumes on new inputs without code changes.
- No mutation of `_legacy/` code; new engine runs independently.
- All tests pass in CI.

---

## Follow-Ups (Next PRPs)
- **PRP-GPP-02:** Ownership/field realism (strength buckets, chalk tilt, late news).
- **PRP-VB-02 / PRP-FS-02:** Controls to target dup-risk and top-1% hit-rate, calibrated against sim metrics.
- **PRP-DASH-01:** Unified dashboard routes & data orchestration.

---

## GitHub Actions (End)
- `git add -A && git commit -m "feat(gpp): minimal contest simulator vertical slice"`
- `git push -u origin HEAD`
- Open PR: `gh pr create -B main -t "feat(gpp): minimal contest simulator (vertical slice)" -b "Adds minimal GPP sim with stable I/O and metrics."`
- Merge when green → `git switch main && git pull --ff-only`
