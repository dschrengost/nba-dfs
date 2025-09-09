
# PRP-VB-01 (v2) — Variant Builder Contract (Aligned with Optimizer + Injection Model)

“This PRP supersedes PRP-VB-01 (v1). The v1 document should be removed to avoid conflicts.”

**Owner:** Cloud Agent  
**Repo:** `nba-dfs`  
**Status:** Supersedes VB-01 (v1); explicitly depends on Optimizer outputs.

---

## Inputs
- `optimizer_run.jsonl` (authoritative): produced by OPTO; each record contains a **validated** lineup by `player_id`, salary, and diagnostics/objective metadata.
- Optional: canonical pool from `projections.csv` + `slate.csv` (for replacements/perturbations).

## Output (for injection)
- `variant_catalog.(jsonl|parquet)` — **our entries**. Each row:
  - `lineup: [player_id...]`, `salary_total`, `teams`, `valid=True`, `tags` (e.g., leverage, stacks, exposure class)
  - Provenance: `run_id`, `created_at`, `site`, `slate_id`, `source_branch`

## Validator
- VB must import **`validators/lineup_rules.py`** (single source of truth).
- All produced lineups pass the same validator FS uses; no ID remaps.

## Interaction with FS (Injection)
- FS builds `field_base.jsonl` **independently**.
- Injection merges `variant_catalog` with tags: `source="injected"`, `origin="variant_catalog"`, `owner="us"`.
- FS re-validates merged entries using the same validator.

## Acceptance
- Round-trip validation passes on mini-slate fixture.
- VB respects OPTO’s contracts; `optimizer_run.jsonl` → `variant_catalog` without rule drift.
- FS injection succeeds without mutation; metadata preserved.
