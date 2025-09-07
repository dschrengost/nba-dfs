When you finish a change:

1) Sync env
- `uv sync`

2) Quality gates (blocking)
- `uv run ruff .`
- `uv run black --check .`
- `uv run mypy .`
- `uv run pytest -q`

3) Contracts & Tests
- If schemas changed/added: add tests under `tests/schemas/` and update docs.
- Ensure dk_player_id persists through any new dataframes or artifacts.

4) Determinism
- Thread `seed` through new stochastic functions; ensure it is recorded in run metadata where applicable.

5) Safety & Hygiene
- Verify no writes under `data/raw/` or `runs/` without a slate key.
- Keep changes minimal and scoped; follow conventional commits.

6) PR Prep
- Fill PR template: scope, impacted modules, data contracts changed (Y/N + migration), determinism verified, CI gates checked, rollback plan.
- Target `dev` for integration; no direct commits to `main`.