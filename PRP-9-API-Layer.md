# PRP-9: API Layer

## Purpose
Expose the orchestrator and artifacts through a REST API for programmatic access and future UI integration.  
Goal: reproducible runs via HTTP, artifact retrieval, health checks.

## Scope
- **Module**: `processes/api/` (FastAPI app)
- **Endpoints**:
  - `POST /orchestrate` → trigger orchestrator run (params: slate_id, config)
  - `GET /runs/{run_id}/bundle` → return bundle.json
  - `GET /runs/{run_id}/artifacts/{kind}` → stream parquet/JSON artifacts
  - `GET /metrics/{run_id}` → fetch metrics (depends on PRP-8)
  - `GET /health` → service health check
- **Startup**:
  - `uv run uvicorn processes.api.main:app --reload`
- **Artifacts served**: projections, lineups, variants, field, sim, metrics, DK export
- **Docs**: auto-generated OpenAPI via FastAPI

## Key Features
- Orchestrator invocation from API
- Deterministic run_ids preserved
- Streaming artifact downloads
- Optional auth placeholder for future multi-user

## Tests
- Smoke test: `GET /health` returns 200
- Orchestrator run via `POST /orchestrate` produces a bundle.json
- Retrieval of artifacts returns correct schema
- Golden test: known sim run returns consistent metrics

## Dependencies
- Depends on orchestrator (PRP-6) and metrics (PRP-8 for /metrics).
- Exposes foundation for UI integration (PRP-10+).
