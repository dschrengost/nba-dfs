# PRP-11: Expanded API Endpoints for DFS Pipeline

## Purpose
Extend the FastAPI service (`processes/api/app.py`) with additional endpoints to expose the DFS pipeline stages more fully, aligning with the MVP and unified dashboard requirements.

## Scope / Application
- Applies to the API layer only (`processes/api`).
- Adds endpoints to orchestrate and retrieve results from ingest, optimizer, variants, field sampler, simulator, metrics, and DK export runs.
- No schema changes required — endpoints reuse existing Pydantic models and adapters.
- Will support the upcoming unified dashboard.

## Definitions
- **Bundle**: An orchestrated run combining multiple stages (ingest → optimizer → variants → field → sim → metrics).
- **Manifest**: JSON artifact describing a run and its outputs.
- **Stage**: A single process (optimizer, variants, field, sim, etc.).

## Responsibilities
- **API Layer**: Expose clean REST endpoints for all pipeline stages.
- **Adapters**: Continue handling the heavy lifting (already schema‑validated).
- **Tests**: Cover all new endpoints with request/response validation.

## Procedure Instructions
### Endpoints to Add
- `POST /run/ingest` → Trigger ingest adapter; returns run_id + manifest.
- `POST /run/optimizer` → Trigger optimizer adapter; returns run_id + manifest.
- `POST /run/variants` → Trigger variants adapter; returns run_id + manifest.
- `POST /run/field` → Trigger field sampler; returns run_id + manifest.
- `POST /run/sim` → Trigger GPP simulator; returns run_id + manifest.
- `POST /run/metrics` → Trigger metrics adapter; returns run_id + manifest.
- `POST /run/dk-export` → Trigger DK export; returns path to DK CSV.
- `GET /runs/{run_id}` → Already exists; validate with Pydantic `BundleManifest`.
- `GET /metrics/{run_id}` → Already exists; validate with schema.

### Contracts
- All `POST /run/*` endpoints accept a Pydantic request model (config + paths).
- Responses include run_id, manifest_path, and any primary outputs.
- Errors return FastAPI `HTTPException` with clear messages.

## Acceptance Criteria
- [ ] All endpoints implemented in `processes/api/app.py` with Pydantic validation.
- [ ] Endpoints call the correct adapter functions with proper schema paths.
- [ ] New tests added in `tests/test_api_endpoints.py` covering all endpoints.
- [ ] Lint/type/format checks (`ruff`, `black`, `mypy`) pass on `processes/api`.
- [ ] `uv run pytest -q tests/test_api_*py` passes with all endpoints tested.
- [ ] Unified dashboard can call these endpoints without additional backend work.

## References
- PRP-10/11: API + Pydantic models
- PRP-7: Orchestrator
- PRP-8: Metrics Framework

## Revision History
- v0.1.0: Initial draft (expand API endpoints to cover full pipeline).
