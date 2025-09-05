# PRP-3a: Variants Adapter — polish & hardening

## Status
**Planned** — follow-up to PRP-3. Tighten contracts, improve validation and UX, no core algorithm changes.

---

## Objective
Make the variants adapter more robust and explicit by:
- Using a precise `inputs.role` for the optimizer-lineups input in the **manifest**,
- Adding stronger variant sanity checks (duplicates and optional salary cap),
- Hardening registry discovery and YAML config parsing,
- Clarifying **seed precedence** and CLI help,
- Extending tests/README accordingly.

---

## Start Bookend — Branch
```
PRP Start → branch=feature/variants-polish
```

---

## Scope & Deliverables

### A) Code changes (no UI)
**File:** `processes/variants/adapter.py`

1. **Manifest inputs.role**
   - Set the role for the optimizer lineups input to **`"optimizer_lineups"`** instead of `"variants"`.
   - If the current manifest schema enum doesn’t yet include this value, use a temporary value **`"artifact"`** and add a `TODO(PRP-3a)` to switch to `"optimizer_lineups"` once the enum is extended. Prefer `"optimizer_lineups"` if schema already allows it.

2. **Variant sanity checks**
   - Keep `len(players) == 8`.
   - Add **duplicate player** guard: error if `len(set(players)) != 8`.
   - If a variant provides a `total_salary` (int/float), **ensure ≤ 50000**. Treat missing or non-numeric gracefully (skip cap check).

3. **Registry discovery hardening**
   - In `_find_input_optimizer_lineups`, assert the registry DataFrame has columns `{"run_type","slate_id","created_ts"}` before filtering; otherwise raise a clear error that hints to re-run optimizer for this slate.

4. **YAML parsing errors**
   - In `load_config`, catch parser exceptions and raise a friendly `ValueError` indicating the file path and the first YAML error message.

5. **Seed precedence doc**
   - Keep passing `seed` as a dedicated argument to the variant function, and include `seed` inside `knobs` (backward compat). Document: **function arg takes precedence** if both are present.

6. **CLI help clarifications**
   - Update help string for `--from-run` to say: “Optimizer run_id to source lineups from (run_type=optimizer).”
   - In `--verbose` mode, print a one-liner that includes the chosen input path, run_id (if derived), and variant count.

### B) Tests
Add/modify tests under `tests/`:

1. **Duplicate players fail-fast**
   - `test_variants_failfast_duplicate_players.py`: stub variant builder returns a variant with a duplicate player; assert that **no artifacts/manifest/registry** are written.

2. **Salary cap check (optional)**
   - `test_variants_failfast_salary_cap.py`: stub variant includes `total_salary=50001`; assert fail-fast.

3. **Registry hardening**
   - `test_variants_registry_missing_columns.py`: create a minimal registry with missing `created_ts`; assert the adapter raises a helpful error.

4. **Manifest inputs.role**
   - Adjust `test_variants_manifest_registry.py` to assert `inputs[0].role == "optimizer_lineups"` when schema supports it; otherwise assert `"artifact"` and leave a TODO comment referencing this PRP.

5. **YAML parse error message**
   - `test_variants_bad_yaml_config.py`: write malformed YAML; assert raised `ValueError` contains the config path and a short parse message.

6. **Verbose breadcrumb**
   - Extend `test_variants_verbose_and_schemas_root.py` to assert the verbose line includes the chosen optimizer lineups path and variant count.

### C) Docs
- **`processes/variants/README.md`**:
  - Note `export_csv_row` is a **preview** (not DK-uploadable).
  - Document seed precedence (function arg wins over `knobs.seed`).
  - State the input discovery policy and the registry column requirement.
  - Mention the new `inputs.role = "optimizer_lineups"` (or temporary `"artifact"` if the enum isn’t yet extended).

### D) Optional (if schema supports role extension now)
- If you choose to extend enums in this PRP:
  - Bump `pipeline/schemas/common.types.yaml` version: add `"optimizer_lineups"` to the appropriate `InputRoleEnum` (or introduce one).
  - Bump `manifest.schema.yaml` version and update examples.
  - Update tests accordingly.
  - Otherwise, defer this enum change to a separate, tiny schema PRP.

---

## Acceptance Criteria
- Variants adapter rejects duplicates or salary-cap-violating variants (fail-fast, no partial writes).
- Manifest input role accurately reflects the source artifact.
- Registry discovery fails with a clear message when the registry is malformed.
- YAML errors are user-friendly and include the config path.
- README and help text reflect seed precedence and discovery rules.
- All new/updated tests pass locally and in CI.

---

## CI Hooks
Extend the existing workflow to include the new tests:
```yaml
on:
  pull_request:
    paths:
      - "processes/variants/**"
      - "tests/test_variants_*py"
      - "processes/optimizer/**"           # if helpers are shared
      - "pipeline/schemas/**"              # only if you bump schema enums
jobs:
  test:
    steps:
      - run: uv run ruff check processes/variants tests
      - run: uv run black --check processes/variants tests
      - run: uv run mypy processes/variants tests
      - run: uv run pytest -q tests/test_variants_*py
      - run: uv run python -m processes.variants --help
```

---

## End Bookend — Merge & Tag
```
PRP End → branch=feature/variants-polish
```
(Manual)
```bash
git checkout main
git merge --no-ff feature/variants-polish -m "PRP-3a: Variants adapter polish & hardening"
git push origin main
git tag -a v0.4.1 -m "PRP-3a: Variants adapter polish"
git push origin v0.4.1
```
