
# PRP-FS-01 — Field Sampler (Injection Model, Top-Level Spec)

**Owner:** Cloud Agent  
**Repo:** `nba-dfs`  
**Branch:** `feat/fs-01-injection`

---

## Intent
Build a **realistic field** from projections/ownership rules (not from our variants), then **inject our Variant Catalog** as our entries. This decouples *field realism* from our strategies.

## Inputs
- `projections.csv`: `player_id, player_name, team, positions, salary, proj_pts, minutes` (+ optional ownership columns)
- `slate.csv`: `player_id, team, opp, game_id, is_active`
- `contest_config.json`: `site, sport, salary_cap, roster_slots[], max_per_team, multi_pos_sep, allow_util, allow_multi_pos`
- `variant_catalog.(jsonl|parquet)` (optional for injection step; treated as **our** entries)

## Outputs
- `artifacts/field_base.jsonl` — sampled public field (valid lineups only)
- `artifacts/field_merged.jsonl` — `field_base` + injected `variant_catalog` (w/ provenance tags)
- `artifacts/metrics.json` — counts, exposures, dupe estimates, invalid-attempt ratios
- `artifacts/audit_fs.md` — compliance report (0 critical violations target)

## Rules & Validation (must use **shared validators**)
- Roster size, eligibility (incl. UTIL), salary cap, max-per-team, no duplicates, active status.  
- Config-driven; DK NBA preset available; no hardcoding.

## Sampling (public field)
- Weighted by projections and/or ownership priors (`p ∝ own^α`), optional team stack preferences.
- Deterministic RNG (seeded). Rejection sampling with structured invalidation reasons.

## Injection
- Append our `variant_catalog` into the field with tags: `source="injected"`, `origin="variant_catalog"`, `owner="us"`.
- Ensure no ID mutation; revalidate lineups via the same validator.
- Optionally cap injected count or replace equal number of base-field lineups (config).

## Acceptance Criteria
1. `field_base.jsonl` and `field_merged.jsonl` contain **only validator-approved** lineups.
2. Artifacts include required metadata (`run_id`, `created_at`, `site`, `slate_id`, `seed`, `ruleset_version`).
3. `audit_fs.md` shows 0 criticals on mini-slate fixture and one real slate.
4. Deterministic reproduction with fixed seed + config.

## GitHub Actions
**Start:** create `feat/fs-01-injection`, commit scaffolds, push, open Draft PR  
**End:** CI green; audit updated; rebase; squash-merge; tag `v0.4.0-fs-injection`
