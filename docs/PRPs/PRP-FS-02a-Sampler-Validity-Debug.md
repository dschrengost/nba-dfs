# PRP-FS-02a — Field Sampler Validity Debug (Targeted)

## Goal
Resolve the **0/5000 valid lineups** issue in `SamplerEngine` on the mini slate by fixing candidate generation and legacy-compat behavior so tests pass without weakening assertions.

## Scope (tight)
- **Sampler only**: `processes/field_sampler/**` (+ minimal test harness edits if strictly needed).
- No edits to golden expectations; do **not** change test thresholds unless explicitly stated below.
- Keep `_legacy/` untouched.

## Hypothesis (most likely culprits)
1. **Eligibility intersection type bug**: `'list' & set` errors avoided earlier; but remaining logic may still treat allowed positions as list or reorder candidates.
2. **Order stability**: filtering via sets or sorts changed candidate order before `shuffle`.
3. **Slot order drift**: iterating slots in non-DK order yields harder states.
4. **Over-zealous pre-constraints**: `TeamLimiter` / `SalaryManager` rejecting too early on tiny fixtures.

## Tasks
1) **Instrument (temporary)**
   - Add a local-only debug harness (or quick script) to sample **500 attempts** with `seed=1`, counting validator error codes.
   - Print top 10 failure reasons; then remove before final commit.

2) **Fix candidate filtering**
   - Ensure **allowed positions are sets**: `allowed: set[str]`.
   - Parse player positions to `set[str]` (treat NaN → `set()`).
   - Build candidates by preserving **pool order**, then shuffle:
     ```py
     # pool: ordered list of player_ids
     candidates = [pid for pid in pool if allowed & pos_of(pid)]
     rng.shuffle(candidates)
     ```

3) **DK slot order**
   - Iterate slots in this exact order: `["PG","SG","SF","PF","C","G","F","UTIL"]`.

4) **Guard constraints (mini slate)**
   - Start with `salary_cap=50000`, `max_per_team=5` in tests/harness.
   - Ensure `TeamLimiter` and `SalaryManager` don’t consume RNG or reorder pools in compat path.

5) **Compat RNG (if applicable within FS-02)**
   - Single `rng = random.Random(seed)` passed everywhere.
   - Only `rng.shuffle` consumes randomness in compat path.
   - Deterministic pre-sorts prior to first RNG call.

## Acceptance Criteria
- On `tests/fixtures/mini_slate.csv`, `SamplerEngine(..., seed=1)` produces **≥ 1 valid lineup** within 5,000 attempts.
- Property test **passes without lowering success threshold** (target ≥ 1% unless the fixture is proven otherwise via metrics).
- Golden test remains unchanged and passing (if compat mode exists); otherwise property test passes and golden is unaffected.

## Deliverables
- Minimal diffs in `processes/field_sampler/` correcting candidate filtering & slot order.
- (Optional) A temporary triage script or pytest `-s` output demonstrating top failure reasons; removed in final commit.
- Short README note in `docs/field_sampler/README.md` explaining slot order, eligibility typing, and determinism knobs.

## Test Plan
```bash
uv run ruff check processes/field_sampler
uv run black --check processes/field_sampler
uv run mypy processes/field_sampler
uv run pytest -q tests/test_field_sampler_engine.py
```
If needed during triage:
```bash
uv run pytest -q -k field_sampler_engine -s
```

## Out of Scope
- Changing golden expected lineups.
- Relaxing assertions permanently (thresholds) unless data proves fixture is insufficient; if so, add a one-paragraph rationale in the PR body.

## Git Workflow
- **Start**
  ```bash
  git switch -c feat/fs-02a-sampler-validity
  ```
- **Commit & Push**
  ```bash
  git add processes/field_sampler
  git commit -m "fix(field-sampler): candidate filtering + slot order for valid outputs (PRP-FS-02a)"
  git push -u origin feat/fs-02a-sampler-validity
  ```
- **Open PR**
  ```bash
  gh pr create -B main     -t "fix(field-sampler): restore validity on mini slate (PRP-FS-02a)"     -F docs/PRPs/PRP-FS-02a-Sampler-Validity-Debug.md
  ```

## Notes for Reviewer
- Verify candidate order preservation prior to `rng.shuffle` and confirm slots iterate in DK order.
- Ask for a 10-line debug paste (attempts histogram) if flakiness persists.
