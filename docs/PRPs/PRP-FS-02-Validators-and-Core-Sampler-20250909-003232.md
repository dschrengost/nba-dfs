
# PRP-FS-02 — Shared Validators + Core Sampler Engine

**Owner:** Cloud Agent  
**Repo:** `nba-dfs`  
**Branch:** `feat/fs-02-core`

---

## Deliverables
- `validators/lineup_rules.py` (single source of truth): eligibility (incl. UTIL), salary cap, roster size, max-per-team, no duplicates, active status.
- `field_sampler/engine.py` with `SamplerEngine.generate(n)`:
  - `PositionAllocator`, `SalaryManager`, `TeamLimiter`, `RejectionSampler`
  - deterministic RNG; tiered/ownership-weighted sampling; stack knobs
- IO contracts:
  - Inputs: `projections.csv`, `slate.csv`, `contest_config.json`
  - Outputs: `artifacts/field_base.jsonl`, `artifacts/metrics.json`
- Minimal CLI: `python -m tools.sample_field` (smoke) using the engine + validators.
- Docs: `docs/USAGE-field-sampler.md` (examples, config).
- Tests: unit (parsers/boundaries), property (hypothesis), golden fixtures; regression for past eligibility/salary bug.

## Constraints
- No validation duplication; import from `validators/lineup_rules.py` everywhere.
- Config-driven; DK preset lives in `config/site_rules.py`.
- DK IDs preserved throughout.

## Acceptance
- 100% sampler outputs pass the shared validator.
- Property tests: 0 validator-escape events across 50k candidates (synthetic slate).
- Golden mini-slate produces valid lineups; past bug cannot pass.
- Artifacts carry required metadata and pass schemas.
- `audit_fs.md` updated to 0 criticals.

## GitHub Actions
**Start:** create `feat/fs-02-core`, push, Draft PR  
**End:** CI green; audit updated; rebase; squash-merge; tag `v0.4.1-fs-core`
