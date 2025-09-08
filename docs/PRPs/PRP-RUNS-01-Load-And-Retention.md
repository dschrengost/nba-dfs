# PRP-RUNS-01 — Load Previous Runs + Retention/Pruning
**Date:** 2025-09-08 01:26  
**Owner:** Daniel S.  
**Repo:** `nba-dfs` (monorepo)  
**Scope:** Optimizer runs (extendable to sampler/sim later)  
**Status:** Draft for implementation

---

## 1) Why
We need a first-class way to **load prior optimizer runs** and a **simple retention policy** so we don’t hoard old artifacts. For optimizer runs, **keep the last 10** (MRU) and **prune on save**.

---

## 2) Goals (Acceptance Criteria)
- A user can open a **“Load Run”** UI and select from the **last 10 optimizer runs** (most recent first).
- Loading a run restores: parameters, lambda/ownership settings, seed, pool metrics, and references to artifacts (CSV/JSON).
- Saving a new optimizer run **automatically prunes** older runs beyond the configured limit (default 10).
- A **CLI** and **REST** surface exist for listing, loading, saving, and pruning runs.
- All new logic covered by unit tests; e2e happy-path test loads a saved run and verifies store state matches saved meta.

---

## 3) Non-Goals
- Long-term archival and cloud sync (future work).
- Cross-slate portability guarantees (we will warn if slate key / player-id universe differs).

---

## 4) Storage & Data Model
### 4.1 Directory Layout (local disk)
```
data/
  runs/
    optimizer/
      20250907_201455__main/         # run_id dir
        run_meta.json                 # canonical metadata
        inputs/                       # captured inputs (projections.csv, config.json, etc)
        outputs/                      # lineups.csv, telemetry.json, diagnostics.json
    index/
      optimizer_index.json            # MRU list (derived but cached for fast UI)
```

### 4.2 `run_meta.json` (schema sketch)
```json
{
  "run_id": "20250907_201455__main",
  "type": "optimizer",
  "created_at": "2025-09-07T20:14:55Z",
  "tag": "scenario1", 
  "slate_key": "2025-10-28-DK-10g",
  "engine": {
    "solver": "cp-sat",
    "seed": 42
  },
  "params": {
    "uniques": 2,
    "ownership_penalty": {
      "enabled": true,
      "lambda": 8.0,
      "curve": "by_points"
    }
  },
  "inputs": {
    "projections_csv": "inputs/projections.csv",
    "player_ids_csv": "inputs/player_ids.csv",
    "config_json": "inputs/config.json"
  },
  "artifacts": {
    "lineups_csv": "outputs/lineups.csv",
    "diagnostics_json": "outputs/diagnostics.json",
    "telemetry_json": "outputs/telemetry.json"
  },
  "diagnostics": {
    "pool": {
      "lineups": 150,
      "avg_pairwise_jaccard": 0.57,
      "unique_player_count": 98
    },
    "ownership_penalty": {
      "applied": true,
      "lambda_used": 8.0
    }
  }
}
```

### 4.3 MRU Index (`optimizer_index.json`)
```json
{
  "type": "optimizer",
  "limit": 10,
  "runs": ["20250907_201455__main", "20250907_185930__main", "..."]
}
```

---

## 5) Public Surfaces
### 5.1 REST (Next.js API routes or FastAPI—keep consistent with repo)
- `GET /api/runs?type=optimizer&limit=10` → MRU runs (reads index; falls back to fs)
- `GET /api/runs/{run_id}` → returns `run_meta.json`
- `POST /api/runs/save` → body: `run_meta` (+ server writes artifacts if passed/paths)
- `POST /api/runs/prune?type=optimizer&keep=10` → prunes oldest beyond `keep`
- `DELETE /api/runs/{run_id}` → removes directory & updates index
- `GET /api/runs/validate/{run_id}` → optional: checks slate_key/player universe compatibility

### 5.2 CLI (uvx entry point)
- `uv run python -m tools.runs list --type optimizer --limit 10`
- `uv run python -m tools.runs load --id 20250907_201455__main`
- `uv run python -m tools.runs prune --type optimizer --keep 10`

---

## 6) Frontend UX
- **Load Run** button → modal with **MRU list** (max 10). Columns: date/time, tag, slate, solver, uniques, λ, pool stats.
- Quick filter by `tag` and `slate_key`.
- Selecting a run hydrates `useRunStore()` with:
  - `summary` (diagnostics/telemetry)
  - `params` (ownership, uniques, seed, etc.)
  - file refs for download/open in viewer
- Show a **compatibility chip** (OK / Mismatch) based on current slate vs run `slate_key`.

---

## 7) Retention Policy & Pruning
- Default: **optimizer.keep = 10** (configurable in `config/runs.yaml`).
- **On save**: append run to MRU; if count > keep → prune oldest by filesystem mtime (or meta.created_at).
- **Idempotent & safe**: skip if directory missing; ignore non-optimizer runs.
- Optional daily cron (`scripts/pyopt/cleanup_old_runs.py`) for belt-and-suspenders.

**Pseudo-code (prune):**
```python
def prune(type: str = "optimizer", keep: int = 10):
    runs = sorted(list_dirs(f"data/runs/{type}"), key=mtime, reverse=True)
    for old in runs[keep:]:
        rm_rf(old)
    write_index(type, [basename(p) for p in runs[:keep]])
```

---

## 8) Implementation Plan (Small, linear steps)
1. **Scaffold**: `src/runs/` python lib with fs helpers; `data/runs/index/` writer/reader.
2. **Write meta** on optimizer completion; ensure `run_id` deterministic (`YYYYMMDD_HHMMSS__branchOrTag`).
3. **MRU index**: build-on-save; on first run, rebuild from fs for robustness.
4. **Prune on save** (configurable keep N); expose CLI entry points (uv scripts).
5. **API routes** mirroring CLI.
6. **UI modal** to browse + load → hydrate `useRunStore()`.
7. **Compat check** and warning toast if slate mismatch.
8. **Tests**: unit (fs ops, index integrity, prune idempotency), integration (save→load), e2e (UI click loads expected state).
9. **Docs**: README section + usage examples.

---

## 9) Testing Strategy
- **Unit**: temp dirs with >10 fake runs; verify prune removes oldest and index matches.
- **Contract**: `run_meta.json` schema validation (jsonschema) + required fields.
- **Integration**: save a run → load via API → hydrate store → assert UI state (Playwright or Vitest + msw).
- **Regression**: ensure run IDs are unique per save even across concurrent runs.

---

## 10) Config
`config/runs.yaml`:
```yaml
optimizer:
  keep: 10
  base_dir: "data/runs/optimizer"
  index: "data/runs/index/optimizer_index.json"
```

---

## 11) Risks & Mitigations
- **Disk bloat**: prune on save + optional cron.
- **Schema drift**: version `run_meta.schema_version` and provide migration shim.
- **Slate mismatch**: warn, allow “force load” with remap if player ID universe changed.

---

## 12) GitHub Actions (begin/end)
**Start:**
- Create branch: `feature/runs-01-load-and-retain`
- Open WIP PR targeting `main`

**End:**
- Rebase on `main`, squash-merge PR
- Tag: `runs-01` (optional) and update `CHANGELOG.md`

---

## 13) Minimal Stubs (illustrative only)
```python
# src/runs/api.py
def save_run(meta: dict) -> str: ...
def get_run(run_id: str) -> dict: ...
def list_runs(type: str = "optimizer", limit: int = 10) -> list[dict]: ...
def prune_runs(type: str = "optimizer", keep: int = 10) -> None: ...
```

---

## 14) Done = Shipped
- UI can load a selected past run, and the system automatically keeps only the last 10 optimizer runs.
- Tests green; docs updated.


---

## 4.4 Uploads Persistence (Projections & Player IDs) — **Newest Wins**
We will persist all projection and player-id uploads with deterministic filenames and a manifest. **The most recent upload always takes precedence** for the current slate unless a run explicitly snapshots older inputs.

### Directory Layout
```
data/
  uploads/
    projections/
      2025-09-07T20-59-00Z__slate-2025-10-28-DK-10g.csv
      2025-09-07T21-10-12Z__slate-2025-10-28-DK-10g.csv  # newest → active
    player_ids/
      2025-09-07T19-45-11Z__global.csv
      2025-09-07T21-11-03Z__global.csv                   # newest → active
  manifests/
    uploads_manifest.json
```

### `uploads_manifest.json` (schema sketch)
```json
{
  "schema_version": 1,
  "active": {
    "projections": {
      "slate_key": "2025-10-28-DK-10g",
      "path": "data/uploads/projections/2025-09-07T21-10-12Z__slate-2025-10-28-DK-10g.csv",
      "uploaded_at": "2025-09-07T21:10:12Z"
    },
    "player_ids": {
      "scope": "global",
      "path": "data/uploads/player_ids/2025-09-07T21-11-03Z__global.csv",
      "uploaded_at": "2025-09-07T21:11:03Z"
    }
  },
  "history": {
    "projections": ["...older paths..."],
    "player_ids": ["...older paths..."]
  },
  "limits": {
    "projections_per_slate_keep": 10,
    "player_ids_keep": 10
  }
}
```

### Rules
- **Newest wins**: the `active` entry points to the latest file for each category.
- **Per-slate projections**: projections are keyed by `slate_key`; we keep a per-slate MRU list (default keep=10).
- **Global player IDs**: single MRU chain (default keep=10).
- **On run save**: the optimizer **snapshots** the active uploads (stores relative paths in `run_meta.inputs.*`) so the run is reproducible even if newer uploads appear later.
- **Validation**: on load, warn if snapshot inputs are not the current `active` ones; offer one-click **Remap to Active**.

---

## 5.3 REST & CLI for Uploads
### REST
- `POST /api/uploads/projections` → form-data file + `slate_key`; updates manifest; prunes per-slate beyond keep.
- `POST /api/uploads/player_ids` → form-data file; updates manifest; prunes beyond keep.
- `GET /api/uploads/active` → returns current active files & metadata.
- `GET /api/uploads/history?type=projections&slate_key=...` → MRU list for that slate.
- `POST /api/uploads/set-active` → optional endpoint to pin a specific historical file as active (advanced).

### CLI (uv)
- `uv run python -m tools.uploads add-projections --slate SLATE --path file.csv`
- `uv run python -m tools.uploads add-player-ids --path file.csv`
- `uv run python -m tools.uploads active`
- `uv run python -m tools.uploads prune --type projections --slate SLATE --keep 10`
- `uv run python -m tools.uploads prune --type player_ids --keep 10`

---

## 2) Goals (Acceptance Criteria) — **Additions**
- Latest **projections** and **player IDs** persist on disk; **newest automatically becomes active**.
- Saving a run **snapshots** the active uploads into `run_meta.inputs.*` and maintains reproducibility.
- Per-slate projections and global player IDs are **pruned** to MRU **keep=10** (configurable).

---

## 6) Frontend UX — **Additions**
- **Uploads panel** in the left nav:
  - Drag-and-drop for projections (requires `slate_key`) and player IDs.
  - Badge showing **Active** vs **Snapshot** for the current run.
  - History dropdown per slate (last 10) with “Set Active” and “Prune Now” actions.
- **RunSummary**: show which uploads were snapshotted; warning chip if not the latest.

---

## 8) Implementation Plan — **Adds**
- `src/uploads/manifest.py`: read/write `uploads_manifest.json`, enforce newest-wins, pruning.
- API routes + CLI wrappers; wire DnD in UI to call endpoints.
- Integrate into optimizer save path: capture `active` uploads → write into `run_meta.inputs`.
- Compat checks: on run load, compare `run_meta.inputs` vs `uploads_manifest.active` → show chip/toast.

---

## 10) Config — **Extend**
```yaml
uploads:
  projections_per_slate_keep: 10
  player_ids_keep: 10
  dir: "data/uploads"
  manifest: "data/manifests/uploads_manifest.json"
```

---

## 9) Testing Strategy — **Adds**
- Upload twice → `active` points to the newer file; history length increments; prune beyond keep.
- Run save snapshots current `active`; later upload does **not** change the snapshot paths in `run_meta`.
- On load, UI shows “Snapshot vs Active” status and allows remap.

---

## 12) GitHub Actions (begin/end) — unchanged
**Start:** `feature/runs-01-load-and-retain`  
**End:** squash, rebase, changelog, tag.

*Updated:* 2025-09-08 01:28

---

# Update v2 — Auto‑Save Runs with Rolling 10 (Drop Oldest on New)
**Timestamp:** 2025-09-08 01:36

## What Changed
- **Auto‑save on completion**: Every optimizer run writes a `run_id` directory + `run_meta.json` automatically. No manual “Save” action.
- **Rolling retention = 10**: When a new run finishes, we **immediately evict** the oldest run so that only **10** optimizer runs exist at any time (FIFO by `created_at` or dir mtime). No separate prune step.

## Acceptance Criteria (supersedes earlier retention wording)
- On run finish: run artifacts are written and the MRU index is updated.
- If count > 10: the **oldest directory is deleted** atomically before the MRU is finalized.
- UI **Load Run** modal always shows at most 10 runs.
- Concurrency-safe: two runs finishing at once still end up with ≤10 total after eventual consistency.

## Implementation Notes
- Replace “prune on save” with **evict on complete** in the optimizer completion hook:
  1) Write to a **temp dir** (`…/__tmp__{run_id}`), then `rename` to final `{run_id}` (atomic on same fs).
  2) Recompute run list sorted by `created_at`/mtime.
  3) If len > 10 → `rm -rf` the **single** oldest and rebuild index.
  4) Persist `optimizer_index.json` (write temp + atomic move to avoid partial writes).
- Keep the **uploads snapshot** behavior unchanged (inputs in `run_meta.inputs.*`).

## REST/CLI Surface Adjustments
- `POST /api/runs/save` becomes **internal**; typical clients do not call it.
- `GET /api/runs` and `GET /api/runs/{run_id}` unchanged.
- Explicit `prune` endpoint is **optional**; keep for maintenance but not used in normal flow.

## Tests
- Create 12 fake runs in sequence → assert only the **last 10** remain and index order matches.
- Concurrency test: simulate two finishes within 100ms; ensure final count ≤10 and both newest present.
- Crash safety: simulate failure between write and index update; next completion pass reconciles to ≤10.
