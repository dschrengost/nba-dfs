# PRP-FS-07 Lint & Test Stabilization (Agent Task)

## Summary
Bring the repo to a clean, reproducible baseline by fixing the surfaced Ruff errors (E722, E741, E402, B904, B017, F401), tightening pytest behavior, and ensuring mypy/CI alignment. Leave legacy modules minimally touched, favoring surgical edits over refactors.

---

## GitHub Actions (start → end)
- **Start:** Branch `feat/fs-07-lint-test-stabilization` from `main`, commit this PRP.
- **End:** Open PR to `main`, squash-merge when green, delete branch.

---

## Scope / Goals
- Ruff: **0 errors** (safe fixes preferred; limited `--unsafe-fixes` allowed once).
- Black: clean with `line-length = 100`.
- Mypy: runs without plugin errors (Pydantic v2 plugin configured).
- Pytest: **collects** without errors; non-critical tests quarantined (skipped) until re-enabled.
- CI: GitHub Actions workflow using `uv` runs ruff/black/mypy/pytest on PR + `main`.

Non-goals: feature refactors, logic changes beyond what’s required to satisfy lints/tests.

---

## Environment & Tooling
- Python **3.11** (already pinned).
- **uv** for dependency management.
- Dev tools ensured in `dev` group: `ruff`, `black`, `mypy`, `pytest`, `pytest-cov`, `types-PyYAML`, `types-requests`, `pydantic`.

Commands baseline:
```bash
uv sync
uv run black . -l 100
uv run ruff check . --fix
uv run ruff check . --fix --unsafe-fixes
uv run ruff check .
uv run mypy
uv run pytest -q
```

---

## Detailed Tasks

### T1 — Ruff config sanity (no blanket ignores)
- Keep `line-length = 100` for Ruff & Black.
- Keep `ignore = ["E501"]` under `[tool.ruff.lint]` (Black owns wrapping).
- Maintain focused per-file ignores only where justified (e.g., legacy).

**Deliverable:** updated `pyproject.toml` with stable lint config and marker registration:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
markers = ["smoke: minimal tests that should always run"]
```

### T2 — Legacy simulator minimal fixes (E722, E741)
**File:** `processes/gpp_sim/_legacy/nba_gpp_simulator.py`  
- Replace **bare** `except:` with `except Exception:` in the following regions (document exact line changes in commit message):
  - ~598, ~859, ~901, ~964, ~1324
- Rename loop variable `l` → `player_id` in region ~767 to address `E741`.

> If changes risk behavior, fallback: add per-file ignores only for this legacy file:
```toml
[tool.ruff.lint.per-file-ignores]
"processes/gpp_sim/_legacy/nba_gpp_simulator.py" = ["E722","E741"]
```
…but prefer code fixes.

### T3 — Adapter raise style (B904)
**File:** `processes/optimizer/adapter.py` (~269–272)  
- Change:
```python
except Exception:
    raise ValueError(f"Invalid lineup salary value: {total_salary}")
```
to:
```python
except Exception as err:
    raise ValueError(f"Invalid lineup salary value: {total_salary}") from err
```

### T4 — CLI import order (E402)
**File:** `scripts/pyopt/optimize_cli.py`  
- Move imports to the top **before** calling `os.environ.setdefault(...)`.
- Minimal structure:
```python
from collections import Counter
from itertools import combinations
import os
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PROJECT_ROOT", _ROOT)
```

### T5 — Tests: ambiguous names & blind exceptions (E741, B017)
- Rename single-letter `l` variables → `lineup` (or `player_id`) in:
  - `tests/test_optimizer_manifest_registry.py` (~14)
  - `tests/test_optimizer_ownership_penalty_flag.py` (~18)
  - `tests/test_optimizer_run_id_determinism.py` (~14)
- Replace `with pytest.raises(Exception):` with the specific exception expected (likely `ValueError`) in:
  - `tests/test_optimizer_failfast_no_write.py` (~51)

### T6 — Unused imports in raggy.py (F401)
**File:** `raggy.py`  
- Remove unused imports (chromadb, PyPDF2, docx.Document). If presence checks are desired, use:
```python
import importlib.util as _il

if _il.find_spec("chromadb") is not None:
    print("✓ ChromaDB installed")
```
(Apply the same pattern for `PyPDF2` and `docx` or remove the block.)

### T7 — Test quarantine gate (temporary)
- Create `tests/conftest.py` with:
```python
import pytest
def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="Temporarily skipped during stabilization (FS-07)")
    for item in items:
        if "smoke" not in item.keywords:
            item.add_marker(skip)
```
- Add `@pytest.mark.smoke` to at least one “happy path” test (e.g., optimizer adapter default, projections verbose print).

### T8 — CI wiring
Create `.github/workflows/ci.yml`:
```yaml
name: ci
on:
  push: { branches: [ main ] }
  pull_request:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/uv-action@v3
      - run: uv python pin 3.11 && uv sync
      - run: uv run ruff check .
      - run: uv run black --check .
      - run: uv run mypy
      - run: uv run pytest -q
```

---

## Acceptance Criteria
- `uv run ruff check .` → **0** errors.
- `uv run black --check .` → passes.
- `uv run mypy` → runs clean (no plugin errors).
- `uv run pytest -q` → **collects** without errors; non-smoke tests are skipped.
- CI is green on branch and on merge to `main`.

---

## Allowed Paths (Agent)
- `pyproject.toml`, `.github/workflows/ci.yml`, `tests/**`
- `scripts/pyopt/optimize_cli.py`
- `processes/optimizer/adapter.py`
- `processes/gpp_sim/_legacy/nba_gpp_simulator.py`
- `raggy.py`

**Do not** refactor logic beyond what’s required to satisfy lint/test constraints.

---

## Commit Plan
1. `chore(ci): add uv-based CI pipeline`
2. `chore(lint): align ruff/black config and pytest markers`
3. `fix(legacy): replace bare excepts and E741 in legacy simulator`
4. `fix(adapter): use exception chaining per B904`
5. `fix(cli): move imports above env setup (E402)`
6. `test: rename ambiguous vars and use specific exceptions`
7. `chore(raggy): drop unused imports or use find_spec checks`
8. `test: add quarantine gate and mark smoke tests`

---

## How to Run (Agent)
```bash
git switch -c feat/fs-07-lint-test-stabilization
uv sync

# iterate tasks T1–T7, running after each:
uv run black . -l 100
uv run ruff check . --fix && uv run ruff check .
uv run mypy
uv run pytest -q

git add -A && git commit -m "<commit-message>"
git push -u origin HEAD

# open PR and ensure CI passes
```
