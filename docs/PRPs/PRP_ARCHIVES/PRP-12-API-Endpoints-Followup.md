# PRP-12: API Endpoints Follow-Up — Robustness & CI Scope

## Purpose  
Address follow-up improvements after PRP-11: Expanded API Endpoints. Focus on error handling, stricter validation, and CI scope.

## Scope / Application  
- **API Layer (processes/api/app.py)**  
  - Harden `/runs`:  
    - Explicitly return 404 if registry parquet missing (instead of empty list).  
  - Harden `/export/dk`:  
    - For variants runs, raise a clear 422 error if `export_csv_row` is missing or malformed.  
  - Add structured logging for each endpoint entry/exit.  

- **Models (processes/api/models.py)**  
  - Add `ErrorResponse` model for consistent 4xx/5xx responses.  
  - Update endpoints to reference `response_model=ErrorResponse | ...` where applicable.

- **Tests (tests/test_api_endpoints.py)**  
  - Add regression tests:  
    - `/runs` → 404 when registry parquet missing.  
    - `/export/dk` → 422 on bad/missing `export_csv_row`.  
    - `/logs` → correct fallback message when no logs exist.  
  - Ensure error responses match `ErrorResponse` model.  

- **CI Workflow**  
  - Broaden path filters to run API tests when `processes/api/**`, `tests/test_api_*`, or `pipeline/schemas/**` change.  
  - Confirm httpx pin `<0.28` remains until we refactor tests away from `AsyncClient(app=...)`.

## Acceptance Criteria  
- All new error conditions produce JSON responses matching `ErrorResponse` schema.  
- Added tests pass reliably on local + CI.  
- Existing endpoints remain backward-compatible.  
- No schema drift (no changes to bundle/manifest enums).  

## Revision History  
- v0.1 (PRP-12 draft): Proposed error handling + CI scope.  
