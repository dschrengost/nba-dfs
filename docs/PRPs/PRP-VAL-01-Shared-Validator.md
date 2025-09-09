# PRP-VAL-01 — Shared DK Lineup Validator (SSOT) + Refactor

**Owner:** Agent  
**Repo:** `nba-dfs`  
**Status:** Proposed  
**Depends on:** Pipeline schema pack (SSOT), existing optimizer/variant builder/field sampler modules

---

## 1) Summary
Create a single-source **validators/lineup_rules.py** that encodes *all* DraftKings lineup validity rules and is imported by **optimizer**, **variant builder**, **field sampler**, and **sim I/O**. Replace scattered validations with this module, add tests, and wire the validator into run artifacts. This eliminates drift and ensures identical contracts across the pipeline.

**Why now:** Repomix audit shows the validator is missing and logic is duplicated across modules, causing rule drift and fragile integration.

---

## 2) Goals / Non-Goals
### Goals
- Implement canonical validator module with pure, typed functions (no I/O).
- Centralize rules: **roster size, slot eligibility, salary cap, team limit, no duplicates, active/injury filters**, and structured error reasons.
- Provide **pydantic** validator schema for results (errors, enumerated codes).
- Refactor **optimizer / variant_builder / field_sampler** to import and use this module exclusively.
- Add tests (unit + integration fixtures) and ensure metrics surface invalid counts by reason.
- Artifact alignment: write `validation_metrics.json` per stage into `runs/<stage>/<run_id>/artifacts/`.

### Non-Goals
- No new sampling algorithms (that’s a separate PRP).
- No UI work (dashboard wiring is a later PRP).

---

## 3) Scope & Deliverables
### Deliverables (code & docs)
- `validators/lineup_rules.py` — core rules, typed.
- `validators/types.py` — enums & dataclasses/pydantic models (e.g., `InvalidReason`).
- `validators/__init__.py`
- Refactors:
  - `processes/optimizer/...` → use shared validator
  - `processes/variant_builder.py` → use shared validator
  - `processes/field_sampler/*` (legacy adapter) → use shared validator on emit
- Tests:
  - `tests/validators/test_lineup_rules.py` (unit)
  - Touchpoints in existing tests to assert shared validator usage
- Docs:
  - `docs/validators/README.md` — rule table, examples, change protocol

### Out of scope
- Field Sampler engine build-out, ownership bias, etc.
- UI polish and run registry UX.

---

## 4) Contracts (Authoritative Rules)
- **Site:** DK (only)
- **Roster:** 8 slots: PG, SG, SF, PF, C, G, F, UTIL
- **Eligibility:** player’s positions must cover assigned slot (multi-pos allowed)
- **Salary Cap:** sum(salary) ≤ 50,000 (configurable via `Rules`)
- **Team Limit:** ≤ 4 players per NBA team (configurable)
- **No Duplicates:** all player IDs unique within a lineup
- **Active Filter:** `is_active == True` and `inj_status ∉ {"OUT","Ineligible"}` if present
- **IDs:** `dk_player_id` is the primary key and must persist end-to-end

**Result model (pydantic):**
```python
class ValidationResult(BaseModel):
    valid: bool
    reasons: list[InvalidReason] = []
    slots: list[str]  # resolved slot map for the lineup
    salary_total: int | None
    teams: dict[str, int] | None
```

**Error reasons (enum, non-exhaustive):**
- `ROSTER_SIZE_MISMATCH`
- `SLOT_ELIGIBILITY_FAIL`
- `SALARY_CAP_EXCEEDED`
- `TEAM_LIMIT_EXCEEDED`
- `DUPLICATE_PLAYER`
- `MISSING_PLAYER`
- `INACTIVE_PLAYER`
- `INJURY_STATUS_BLOCKED`

---

## 5) Public API (module surface)
```python
# validators/lineup_rules.py
from .types import Rules, InvalidReason, ValidationResult

def validate_lineup(
    dk_player_ids: list[str],
    player_pool: dict[str, dict],  # keyed by dk_player_id -> {salary:int, positions:list[str], team:str, is_active:bool?, inj_status:str?}
    rules: Rules,
) -> ValidationResult: ...
```

- **Pure** function: deterministic, no disk/network I/O.
- `Rules` carries roster template, salary cap, team limit, and toggles for active/injury checks.

---

## 6) Refactor Plan
1. **Introduce module** under `validators/` with types, enums, and core logic.
2. **Wire optimizer**: replace local checks with `validate_lineup(...)`; store `validation_metrics.json` (counts by reason).
3. **Wire variant builder**: use shared validator post-generation; drop local `_validate_lineup`.
4. **Wire field sampler (legacy adapter)**: call validator before writing entrants; attach `valid` and drop invalids (metrics recorded).
5. **Schema touch**: ensure any artifacts (lineups/fields) include `valid=True` and optional `invalid_reason` if kept for debugging.
6. **Docs**: rule table + examples; update AGENTS.md pointers to SSOT.

---

## 7) Tests
- **Unit**: hand-crafted lineups to hit each error reason.
- **Property-based (optional)**: slots/teams/salary boundaries.
- **Integration**: mini-slate fixtures through optimizer → VB → sampler; assert identical validator behavior.
- **Gates** (uv):
  - `uv run ruff validators tests/validators`
  - `uv run black --check validators tests/validators`
  - `uv run mypy validators`
  - `uv run pytest tests/validators -q`

---

## 8) Acceptance Criteria
- Single module `validators/lineup_rules.py` exists and exports `validate_lineup` + `Rules`.
- Optimizer, Variant Builder, and Field Sampler **import** and use it (no duplicate rule code left).
- All new tests pass; existing suites unchanged or updated accordingly.
- Each stage writes `validation_metrics.json` with counts by reason.
- DK IDs are preserved in all touched artifacts.
- No new heavy deps; Pydantic remains for models only.

---

## 9) Git & CI Actions
**Start:**
- `git switch -c feat/validators-ssot-01`

**During:**
- Small commits: `feat(validators): add rules & enums`, `refactor(opt): use shared validate_lineup`, etc.
- Keep CI green: ruff/black/mypy/pytest via `uv run`.

**End:**
- `git fetch origin && git rebase origin/main`
- `git push -u origin HEAD`
- Open PR to `main` with before/after rule matrix and metrics screenshots.
- Squash-merge; delete branch.

---

## 10) Rollback Plan
- Revert PR; restore previous validator stubs in modules (kept as orphaned commits).
- Since this is additive and behind clear imports, rollback is low-risk.

---

## 11) Risks / Mitigations
- **Hidden drift** in legacy code paths → **Mitigation:** search & CI checks to block local validators.
- **Fixture churn** in tests → Update fixtures once; document examples in `docs/validators`.

---

## 12) Open Questions
- Should inactive/injury checks be **hard fail** or **configurable** per stage?
- Expose per-slot eligibility overrides (rare edge cases)?
- Emit first-failure only vs. collect-all reasons (current plan: collect-all).

