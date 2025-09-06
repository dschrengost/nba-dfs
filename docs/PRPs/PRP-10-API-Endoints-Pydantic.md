# PRP-10: API Endpoints (FastAPI) — with Pydantic Models (folds PRP-11)

**Status:** Draft  
**Owner:** @you  
**Branch:** `feature/api-pydantic`  
**Goal:** Stand up a small, typed API layer over the existing adapters (ingest → optimizer → variants → field → sim → metrics), using **Pydantic models** for request/response validation and to auto-generate OpenAPI. Replace dict-shaped inputs/outputs with explicit models now to avoid refactors later.

---

## 1) Summary

We will:
- Add/upgrade a FastAPI service under `processes/api/`.
- Define **Pydantic v2** models for all request/response bodies and common data shapes used by our endpoints.
- Implement a **minimal but useful** set of endpoints to trigger the orchestrator, query bundles, list runs, and fetch metrics/summaries.  
- Ensure the API produces **OpenAPI** & **docs** out of the box (`/openapi.json`, `/docs`, `/redoc`).  
- Add tests (httpx + anyio) and wire **CI** (ruff/black/mypy/pytest).

This PRP **combines** the previously separate “add endpoints” (PRP‑10) and “refactor to Pydantic models” (PRP‑11) to avoid double‑work.

---

## 2) Scope

### In scope
- Introduce Pydantic models for all new endpoint payloads.
- Implement endpoints with request/response models (below).
- Preserve in‑memory run index (_RUNS/_METRICS) for now; no DB yet.
- Use adapters exactly as defined by earlier PRPs (orchestrator calls the individual adapters; API calls the orchestrator).

### Out of scope
- AuthN/AuthZ (optional stub).
- Frontend/UX.
- Long‑running background jobs / queues (synchronous launch only).
- New business logic in adapters (no solver/sampler changes).

---

## 3) Endpoints

> Base path examples assume `http://localhost:8000` (FastAPI default with uvicorn).

### 3.1 POST `/run/orchestrator`
Trigger a full bundle run. Writes a `bundle.json` manifest and records stage run_ids. Returns the `bundle_id`, `stages`, and paths recorded.

**Request model:** `OrchestratorRunRequest`
```py
class IngestConfig(BaseModel):
    source: str = "manual"
    projections: str | None = None   # path to projections.csv
    player_ids: str | None = None    # path to player_ids.csv
    mapping: str | None = None       # path to YAML mapping

class OptimizerConfig(BaseModel):
    site: Literal["DK"] = "DK"
    engine: str | None = None
    config: dict[str, Any] | None = None

class VariantsConfig(BaseModel):
    config: dict[str, Any] | None = None

class FieldConfig(BaseModel):
    config: dict[str, Any] | None = None

class Payout(BaseModel):
    rank_start: int
    rank_end: int
    prize: float

class ContestConfig(BaseModel):
    field_size: int
    entry_fee: float
    rake: float
    site: Literal["DK"]
    payout_curve: list[Payout]
    contest_id: str | None = None
    name: str | None = None

class SimConfig(BaseModel):
    config: dict[str, Any] | None = None
    contest: ContestConfig | None = None

class Seeds(BaseModel):
    optimizer: int | None = None
    variants: int | None = None
    field: int | None = None
    sim: int | None = None

class OrchestratorConfig(BaseModel):
    ingest: IngestConfig
    optimizer: OptimizerConfig
    variants: VariantsConfig
    field: FieldConfig
    sim: SimConfig
    seeds: Seeds | None = None

class OrchestratorRunRequest(BaseModel):
    slate_id: str
    config: OrchestratorConfig
    out_root: str = "data"
    schemas_root: str = "pipeline/schemas"
    validate: bool = True
    dry_run: bool = False
    verbose: bool = False
```

**Response model:** `OrchestratorRunResponse`
```py
class StageSummary(BaseModel):
    name: Literal["ingest","optimizer","variants","field","sim","metrics"]
    run_id: str
    primary_output: str | None = None

class OrchestratorRunResponse(BaseModel):
    bundle_id: str
    bundle_path: str
    stages: dict[str, str]            # {stage_name: run_id}
    run_registry_path: str | None = None
```

### 3.2 GET `/runs/{bundle_id}`
Returns the persisted `bundle.json` manifest for a previously created bundle.

**Response model:** `BundleManifest`
```py
class BundleStage(BaseModel):
    name: str
    run_id: str
    primary_output: str | None = None

class BundleManifest(BaseModel):
    bundle_id: str
    slate_id: str
    created_ts: str
    stages: list[BundleStage]
```

### 3.3 GET `/metrics/{sim_run_id}`
Returns the `sim_metrics.parquet` content for a sim run as JSON rows.

**Response model:** `list[dict[str, Any]]` (tabular rows).

### 3.4 GET `/health`
Simple healthcheck; returns `{"ok": true, "version": "...", "time": "..."}`.

---

## 4) Implementation Plan

### 4.1 Project structure
```
processes/api/
  app.py              # FastAPI app w/ Pydantic models & endpoints
  models.py           # Pydantic models (request/response/common)
  __init__.py
  __main__.py         # `python -m processes.api` to run uvicorn

tests/
  test_api_smoke.py   # end-to-end with httpx.AsyncClient
```

### 4.2 Pydantic models
- Use **Pydantic v2** (already in the repo via FastAPI transitive; if not, add).
- Define all models listed above in `processes/api/models.py`.
- Replace `dict[str, Any]` payloads in the API with these models.
- Leverage `.model_dump(mode="json")` when passing config to orchestrator (which still expects file path).

### 4.3 FastAPI app
- Update `processes/api/app.py` to import/use models:
  - `@app.post("/run/orchestrator")` accepts `OrchestratorRunRequest` → returns `OrchestratorRunResponse`.
  - `@app.get("/runs/{bundle_id}")` returns `BundleManifest`.
  - `@app.get("/metrics/{run_id}")` returns `list[dict]` shaped rows.
  - `@app.get("/health")` returns a small JSON status.
- Keep the in‑memory `_RUNS` and `_METRICS` registries as now.

### 4.4 Orchestrator integration
- Serialize `request.config` to a temp JSON file and call `orchestrator.run_bundle(...)` (as today).
- Collect `bundle_id`, `bundle_path`, and stage `run_ids` into the response model.

### 4.5 OpenAPI/Docs
- No additional work: FastAPI will auto‑publish `/openapi.json`, `/docs`, `/redoc` thanks to models.

### 4.6 Config / deps
- Ensure `fastapi`, `httpx<0.28`, and `trio` are in dev group (done in prior PR).
- Add `uvicorn` for local serving if missing (dev only).

### 4.7 Tests
- `tests/test_api_smoke.py`:
  - Use `httpx.AsyncClient(app=app, base_url="http://test")` (requires httpx<0.28).
  - Create tiny CSV fixtures on the fly for ingest (like existing tests do).
  - Monkeypatch adapters to stubs (as in prior API test).
  - Assert 200 responses and shapes match models (Pydantic will auto‑validate).

### 4.8 CI
- `.github/workflows/ci.yml` already exists. Ensure path filters include:
  - `processes/api/**`, `tests/test_api_*py`, `pyproject.toml`

---

## 5) Acceptance Criteria

- [ ] Endpoints implemented with **Pydantic models** (no raw dict payloads).
- [ ] `/run/orchestrator` accepts `OrchestratorRunRequest`, returns `OrchestratorRunResponse` with stage mapping.
- [ ] `/runs/{bundle_id}` returns a valid `BundleManifest`.
- [ ] `/metrics/{sim_run_id}` returns JSON rows derived from `metrics.parquet` (404 if missing).
- [ ] `/health` endpoint returns ok/version/time.
- [ ] **OpenAPI** docs render with explicit schemas at `/openapi.json` and `/docs`.
- [ ] Tests green: `tests/test_api_*py` (httpx async client), plus existing suite unaffected.
- [ ] CI workflow passes on PR.
- [ ] No schema changes required in this PRP.

---

## 6) How to run locally

```bash
# 1) Sync env (dev tools included)
uv sync

# 2) Run tests
uv run pytest -q tests/test_api_*py

# 3) Launch the API
uv run python -m uvicorn processes.api.app:app --reload --port 8000

# 4) Try it
curl -s http://localhost:8000/health | jq
open http://localhost:8000/docs
```

---

## 7) Future Work

- Auth (Bearer token) and rate limiting.
- Background execution / jobs + callbacks.
- Pagination and filtering for metrics/results.
- Persist `_RUNS/_METRICS` to Parquet or SQLite.
- Add additional endpoints for artifacts download (CSV, Parquet).

---

## 8) Checklist for the PR

- [ ] Branch created: `feature/api-pydantic`
- [ ] Models in `processes/api/models.py`
- [ ] Endpoints wired to use models
- [ ] Tests updated/added (`tests/test_api_smoke.py`)
- [ ] CI green
- [ ] PR title: `PRP-10: API Endpoints (FastAPI) — with Pydantic models`
- [ ] PR body links this PRP and includes commands & outcomes
