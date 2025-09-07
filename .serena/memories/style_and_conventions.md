Style & Conventions

- Code Style: black formatting; ruff for lint; mypy for typing. Default: strict typing in src/ for new modules; best-effort elsewhere (AGENTS.md). Docstrings encouraged for public functions/classes.
- Determinism: All stochastic functions accept `seed` and avoid hidden global state. Record `seed` in run_meta.json.
- Data Contracts First: Define/version schemas before using data. No schema drift; any changes require a PRP and tests under tests/schemas/.
- IO Adapters: Validate and log row counts/nulls/dupes; ensure dk_player_id is present and preserved in artifacts.
- Repo Hygiene: Single source of truth in src/ (planned transition). No ad-hoc scripts. Keep changes small and focused.
- Paths & Safety: Never write to data/raw/ or runs/ without a slate key. Agent must not write under data/raw/ or runs/ directly.
- Branching/PRs: Use feat/<slug> branches; PR template must include scope, data contract changes, determinism verification, CI checkboxes, rollback plan. Conventional commits (feat:, fix:, refactor:, docs:, chore:).
- Observability: Log metrics per run to artifacts/metrics.json: row counts, null/dupe rates, coverage, timing, memory peak (if available), legacy_metrics optional.
- Performance: Prefer pure functions, explicit inputs/outputs. Disk cache allowed at data/processed/cache/<slate_key>/<adapter>@<version>/ keyed by (source, version_ts, schema_version).
- Timestamps: Use UTC ISO-8601 for timestamps in data; ensure files/run dirs include timestamps.