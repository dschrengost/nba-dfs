# PRP-RUN-01 — Unified Run Registry / SSOT

**Owner:** Agent  
**Repo:** `nba-dfs`  
**Status:** Proposed  
**Depends on:** Schema pack, validator, processes (opt, VB, FS, sim)

---

## 1) Summary
Implement a consistent run registry system to serve as the single source of truth (SSOT) for all process runs. This ensures reproducibility, easy loading of past runs, and standardized artifact storage.

---

## 2) Goals / Non-Goals
### Goals
- Standardized directory structure under `runs/<slate>/<stage>/<run_id>/`
- Mandatory artifacts: `run_meta.json`, `inputs_hash.json`, `validation_metrics.json`, stage outputs (parquet/CSV)
- Helpers to load and query runs (`lib/run_registry.py`)
- Support replay (rerun with same inputs), tagging, and filtering
- Parquet-backed data layer for efficient reload
- CI checks to enforce artifact creation

### Non-Goals
- Database migrations (file-based only for now)
- UI wiring (to be handled in PRP-UI-01)

---

## 3) Deliverables
- `lib/run_registry.py` (helpers for save/load/query)
- Schema updates for run_meta
- Docs: `docs/runs/README.md` (structure, usage)
- Tests: `tests/test_run_registry.py`

---

## 4) Directory Layout
```
runs/
  2025-01-15-slate123/
    optimizer/2025-01-15T1200Z/
      run_meta.json
      inputs_hash.json
      validation_metrics.json
      outputs.parquet
    variant_builder/...
    field_sampler/...
    simulator/...
```

---

## 5) Acceptance Criteria
- Every stage writes artifacts in correct structure
- Run registry can load/replay any past run
- Validation metrics and inputs hash always present
- Single source of truth maintained
