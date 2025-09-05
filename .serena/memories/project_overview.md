Project: NBA-DFS (nba-dfs)

Purpose: Data pipeline and tools for NBA Daily Fantasy Sports. Focus on deterministic, seed-controlled runs, strict data contracts, and clean repo hygiene.

Tech Stack:
- Python (version: latest on dev box; avoid 3.13-only unless needed)
- Libraries: pandas, duckdb, pyarrow, pydantic, streamlit
- Env/locking: uv (uses uv.lock)
- Lint/Format/Type: ruff, black, mypy (per AGENTS.md; not yet configured in pyproject)

Repo Structure (current):
- pipeline/ — ingestion, normalization, registry, schemas (schemas planned under pipeline/schemas)
- processes/ — optimizer, variant builder, field sampler, simulator
- app/ — future Streamlit/Dash UI
- data/ — parquet store (gitignored; read-only to agent)
- docs/ — PRPs and design notes (e.g., PRP-0 schema pack)
- tests/ — currently empty
- .serena/ — Serena project config

Key Contracts (from AGENTS.md + PRP-0):
- Inputs: projections.csv and player_ids.csv required; normalize to house schemas before downstream use
- House Schemas (versioned, strict; additionalProperties: false): players, slates, projections_raw, projections_normalized, optimizer outputs, variant, field, contest_structure, sim_*; see docs/PRPs/PRP-0_pipeline_schema_pack
- IDs: dk_player_id must persist end-to-end
- Slate Key: YY-MM-DD_HHMMSS (America/New_York)
- Run Registry: each run writes run_meta.json, inputs_hash.json, artifacts/, optional tag.txt under runs/<slate_key>/<stage>

Operating Rules:
- Allowed to edit: src/** (planned), tests/**, configs/**, docs/**; current code dirs: pipeline/, processes/, app/
- Read-only: data/**, runs/**
- Determinism: Every stochastic step accepts seed and records it
- CI gates: uv sync → ruff → black --check → mypy → pytest -q
- Conventional commits; small, reviewed changes; PRP required for schema changes

Open TBDs:
- Typing strictness policy, run pruning policy, legacy metrics to port

Notes:
- PRP-0 instructs creating pipeline/schemas/ with a full schema pack and README. No implementation code in that PRP.
- Current repo lacks configured linters/types; commands listed are the intended gates.