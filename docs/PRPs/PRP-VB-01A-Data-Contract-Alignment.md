# PRP-VB-01A — Variant Builder Data Contract Alignment
**Date:** 2025-09-09  
**Owner:** Daniel S.  
**Repo:** `nba-dfs` (monorepo)  
**Branch Target:** `feature/vb-01a-data-contracts`

---

## 0) GitHub Actions (start → end)
**Start:**  
1) `git switch -c feature/vb-01a-data-contracts`  
2) `gh issue create -t "VB-01A: Data Contract Alignment" -b "Schemas, IO, manifests, run registry integration for Variant Builder"`

**End:**  
1) `gh pr create -B main -t "VB-01A: Data Contract Alignment" -b "Implements schemas, IO layer, manifest + run registry; deterministic RNG; artifact immutability"`  


---

## 1) Purpose
Bring `Variant Builder` into strict alignment with **PRP-VB-01** contracts: **schemas-first I/O, immutable run artifacts, deterministic RNG, and DK `player_id` as the single source of truth**. This PRP **does not** change the core algorithm; it **wraps** the current logic with a clean I/O+schema layer.

## 2) Scope (In / Out)
**In:**  
- Typed **Pydantic** schemas for all VB inputs/outputs/manifests.  
- File layout under `runs/{run_id}/variant_builder/` (Parquet + manifest).  
- Validation of optimizer inputs from `runs/{run_id}/optimizer/lineups.parquet`.  
- Deterministic RNG seed handling (propagate to manifest).  
- **Run registry**/manifest creation (read-only for optimizer, write for VB).

**Out:**  
- New diversification features, exposure caps, ownership penalties (deferred to PRP-VB-01C).  
- UI wiring (covered by PRP-VB-02).

---

## 3) Contracts & Artifacts
### 3.1 Required Inputs (read-only)
- `runs/{run_id}/optimizer/lineups.parquet`  
  - Columns (minimum): `lineup_id:str`, `player_id:str`, `position:str`, `salary:int`, `proj:float`, `team:str`  
- `runs/{run_id}/optimizer/manifest.json`  
  - Fields (minimum): `run_id`, `created_at`, `schema_version`, `seed`, `source_files[]`, `constraints{}`

### 3.2 Outputs (write-once)
- `runs/{run_id}/variant_builder/variants.parquet`  
- `runs/{run_id}/variant_builder/diagnostics.parquet`  
- `runs/{run_id}/variant_builder/manifest.json`

### 3.3 Manifest (VB)
```jsonc
{
  "run_id": "2025-01-15_10-30-02Z",
  "vb_id": "vb_0001",
  "created_at": "2025-01-15T10:45:12Z",
  "schema_version": "vb/1.0.0",
  "seed": 42,
  "algo": "swap-mvp",
  "params": {
    "num_variants": 5000,
    "per_base": false,
    "min_uniques": 2,
    "salary_min": 49500,
    "salary_max": 50000
  },
  "input_artifacts": [
    "runs/{run_id}/optimizer/lineups.parquet",
    "runs/{run_id}/optimizer/manifest.json"
  ]
}
```

---

## 4) Module Layout (added/updated)
```
/src/vb/
  __init__.py
  schemas.py        # Pydantic models (VBRequest, VariantRow, DiagnosticsRow, VBManifest)
  io.py             # read/write + validate optimizer/VB artifacts
  cli.py            # argparse wrapper (build command)  [scaffold only, full wiring later]
  algo_adapter.py   # thin adapter: validate inputs -> call legacy algo -> normalize outputs
/tests/vb/
  fixtures/         # tiny optimizer run fixture
  test_contracts.py # schema + IO roundtrip
  test_smoke.py     # build 50 variants deterministically
```

---

## 5) Schemas (concise skeletons)
> Keep snippets minimal; flesh out in code.

```py
# schemas.py
from pydantic import BaseModel, Field, NonNegativeInt, confloat
from typing import Dict, List, Optional

class VBRequest(BaseModel):
    run_id: str
    num_variants: NonNegativeInt = 1000
    seed: Optional[int] = None
    per_base: bool = False
    min_uniques: int = 1
    salary_min: int = 49500
    salary_max: int = 50000
    locks: List[str] = []
    bans: List[str] = []
    exposure_caps: Dict[str, confloat(ge=0, le=1)] = {}
    team_limits: Dict[str, int] = {}
    proj_noise_std: float = 0.0
    max_dupe_rate: confloat(ge=0, le=1) = 0.05
    schema_version: str = "vb/1.0.0"

class VariantRow(BaseModel):
    variant_id: str
    base_lineup_id: Optional[str]
    slots: List[str]  # slot1..slot8 (player_id)
    salary_total: int
    proj_sum: float
    uniques_vs_base: int
    ownership_penalty: float = 0.0

class DiagnosticsRow(BaseModel):
    variant_id: str
    jaccard_to_pool: float
    dupe_score: float
    rules_violations: Optional[dict] = None

class VBManifest(BaseModel):
    run_id: str
    vb_id: str
    created_at: str
    schema_version: str
    seed: Optional[int]
    algo: str
    params: dict
    input_artifacts: List[str]
```
```py
# io.py (signatures only)
def read_optimizer_pool(run_id: str): ...
def write_variant_catalog(run_id: str, variants_df, diagnostics_df, manifest: dict) -> None: ...
def ensure_paths_immutable(run_id: str) -> None: ...
def validate_df(df, expected_cols: list, name: str) -> None: ...
```

---

## 6) Tasks
1. **Scaffold modules** (`/src/vb/*`) and minimal CLI stub (`vb cli build` → validate only).  
2. **Read optimizer artifacts** → validate columns; forbid remapping of `player_id`.  
3. **Adapter**: convert legacy `variant_builder.py` outputs → **canonicalized** `VariantRow` + `DiagnosticsRow`.  
4. **Write outputs** to `runs/{run_id}/variant_builder/` (Parquet + manifest). Enforce **write-once** and **schema_version**.  
5. **Seed handling**: derive single RNG; echo to manifest.  
6. **Fixtures**: add tiny optimizer run under `/tests/vb/fixtures/demo_run/…`.  
7. **Tests**: contracts roundtrip + deterministic smoke (50 variants, fixed seed).  
8. **CI**: type check + unit tests + Parquet schema check.

---

## 7) Acceptance Criteria
- [ ] `uv run python -m vb.cli build --run-id demo_run --num-variants 50 --seed 7` writes:  
  - `variants.parquet`, `diagnostics.parquet`, and `manifest.json` under `runs/{run_id}/variant_builder/`.  
- [ ] Outputs validate against Pydantic schemas; Parquet columns/typing match spec.  
- [ ] `player_id` preserved exactly; no missing/extra IDs vs. inputs.  
- [ ] Re-running with same seed and inputs yields **identical outputs**.  
- [ ] Attempting to overwrite existing VB artifacts fails with a clear error (immutability).

---

## 8) Risks & Mitigations
- **Legacy drift:** keep core algo untouched; only adapt I/O shapes → easier review.  
- **Schema churn:** pin `schema_version`; gate writes on version match.  
- **Perf**: Parquet with column projection; small fixtures for tests.

---

## 9) Dev Notes
- Prefer **Polars** for Parquet I/O and column projection.  
- All JSON uses `orjson` if available.  
- Keep adapter pure; no side-effects outside `io.py`.  
- Document every module boundary with example payloads.
