# PRP-RUNS-01 — Load Previous Runs + Retention/Pruning
**Date:** 2025-09-08 01:26  
**Owner:** Daniel S.  
**Repo:** `nba-dfs` (monorepo)  
**Scope:** Optimizer runs (extendable to sampler/sim later)  
**Status:** Draft for implementation  
**Aligns With:** `AGENTS.md` §§3, 6, 7, 14

---

## 1) Why
We need a first-class way to **load prior optimizer runs** and a **retention policy** that aligns with `AGENTS.md`:
- Runs live under top-level `runs/` and are organized by `SLATE_KEY`.
- Safety rail: “Block any write under runs/ without a slate key”.
- Retention: “Prune non‑tagged runs after N days (TBD)”.

This PRP specifies loading surfaces and proposes a default retention of **14 days** for non‑tagged runs, enforced per‑module and per‑slate, executed on save and optionally via a periodic job.

---

## 2) Goals (Acceptance Criteria)
- A user can open a **“Load Run”** UI and browse optimizer runs for the selected `SLATE_KEY`, most‑recent first.
- Loading a run restores: parameters, ownership settings, seed, pool metrics, and references to artifacts.
- Saving a new optimizer run triggers **pruning of non‑tagged runs older than `runs.retention_days`** (default 14) under that module/slate.
- A **CLI** and **REST** surface exist for listing, loading, saving, and pruning runs. Listing supports filtering by `module` and `slate_key`.
- All new logic covered by unit tests; e2e happy-path test loads a saved run and verifies store state matches saved meta.

---

## 3) Non-Goals
- Long-term archival and cloud sync (future work).
- Cross-slate portability guarantees (we will warn if slate key / player-id universe differs).

---

## 4) Storage & Data Model
### 4.1 Directory Layout (local disk)
Conform to `AGENTS.md` top-level layout and slate keying.
```
/runs/
  <SLATE_KEY>/                      # SLATE_KEY: YY-MM-DD_HHMMSS (America/New_York)
    optimizer/                      # module (stage)
      <RUN_ID>/                     # eg: 25-09-07_201455__main
        run_meta.json               # canonical metadata (see 4.2)
        inputs_hash.json            # content hashes + schema versions
        artifacts/                  # lineups.csv, metrics.json, logs, etc.
        tag.txt (optional)          # freeform label; prevents pruning
```
Notes:
- All writes occur under a concrete `SLATE_KEY` (satisfies safety rail).
- Keep directory names short and portable; avoid spaces.

### 4.2 `run_meta.json` (schema sketch)
```json
{
  "schema_version": 1,
  "module": "optimizer",
  "run_id": "25-09-07_201455__main",
  "created_at": "2025-09-07T20:14:55Z",
  "slate_key": "25-09-07_171500",
  "tag": "scenario1",
  "engine": { "solver": "cp-sat", "seed": 42 },
  "params": {
    "uniques": 2,
    "ownership_penalty": { "enabled": true, "lambda": 8.0, "curve": "by_points" }
  },
  "artifacts": {
    "lineups_csv": "artifacts/lineups.csv",
    "diagnostics_json": "artifacts/diagnostics.json",
    "telemetry_json": "artifacts/telemetry.json"
  },
  "inputs_hash_path": "inputs_hash.json",
  "diagnostics": {
    "pool": { "lineups": 150, "avg_pairwise_jaccard": 0.57, "unique_player_count": 98 },
    "ownership_penalty": { "applied": true, "lambda_used": 8.0 }
  }
}
```

### 4.3 MRU Listing (derived)
To honor the “runs/ is a registry” concept and avoid extra state, the MRU list is **derived at read time** by scanning `/runs/<SLATE_KEY>/<module>/*` and sorting by `created_at` (from `run_meta.json`) or directory mtime as fallback. Implementations may memoize in‑process but must not persist separate index files under `runs/`.

---

## 5) Public Surfaces
### 5.1 REST (Next.js API routes or FastAPI—keep consistent with repo)
- `GET /api/runs?module=optimizer&slate_key=<key>&limit=10` → MRU runs (derived from fs)
- `GET /api/runs/{slate_key}/{module}/{run_id}` → returns `run_meta.json`
- `POST /api/runs/save` → body: `slate_key`, `module`, `run_meta` (+ server places artifacts)
- `POST /api/runs/prune` → body/query: `module`, `slate_key`, `retention_days` (default from config); prunes non‑tagged older than threshold
- `DELETE /api/runs/{slate_key}/{module}/{run_id}` → removes directory
- `GET /api/runs/validate/{slate_key}/{module}/{run_id}` → optional: checks slate_key/player universe compatibility

### 5.2 CLI (uv entry point)
- `uv run python -m tools.runs list --module optimizer --slate <SLATE_KEY> --limit 10`
- `uv run python -m tools.runs load --slate <SLATE_KEY> --module optimizer --id 25-09-07_201455__main`
- `uv run python -m tools.runs prune --module optimizer --slate <SLATE_KEY> --retention-days 14`

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
- Default: **runs.retention_days = 14** (tracked in `configs/defaults.yaml`).
- Scope: pruning applies to **non‑tagged** runs only (presence of `tag.txt` or non‑empty `run_meta.tag` exempts a run).
- Timing: execute pruning **on save** for the given `slate_key/module`, and optionally via a scheduled job.
- Ordering: identify candidates by `created_at` from `run_meta.json`; fall back to directory mtime.
- Safety: never delete outside `/runs/<SLATE_KEY>/<module>/`; use atomic rename to a temp path before removal if supported.

**Pseudo-code (prune by age):**
```python
from datetime import datetime, timedelta, timezone

def prune(module: str, slate_key: str, retention_days: int = 14) -> int:
    base = Path("runs") / slate_key / module
    if not base.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        if (run_dir / "tag.txt").exists():
            continue
        meta = json.loads((run_dir / "run_meta.json").read_text())
        if meta.get("tag"):
            continue
        created_at = _parse_dt(meta.get("created_at")) or _mtime_dt(run_dir)
        if created_at < cutoff:
            _safe_remove(run_dir)
            removed += 1
    return removed
```

---

## 8) Implementation Plan (Small, linear steps)
1. **Scaffold**: `src/runs/` Python lib with fs helpers; no persisted indices.
2. **Write meta** on optimizer completion; ensure `RUN_ID = YY-MM-DD_HHMMSS__<branchOrTag>`; include `schema_version`.
3. **List/MRU**: derive from fs, sorting by `created_at` with mtime fallback.
4. **Prune on save** using `runs.retention_days`; expose CLI entry points (uv scripts) and REST.
5. **API routes** mirroring CLI with `module` and `slate_key` parameters.
6. **UI modal** to browse + load → hydrate `useRunStore()`.
7. **Compat check** and warning toast if slate mismatch.
8. **Tests**: unit (fs ops, schema validate, prune idempotency), integration (save→load), e2e (UI click loads expected state).
9. **Docs**: README section + usage examples.

---

## 9) Testing Strategy
- **Unit**: temp dirs with mixed ages and tags; verify prune removes only non‑tagged older than cutoff.
- **Contract**: `run_meta.json` schema validation (jsonschema) + required fields.
- **Integration**: save a run → load via API → hydrate store → assert UI state (Playwright or Vitest + msw).
- **Regression**: ensure run IDs are unique per save even across concurrent runs.

---

## 10) Config
Add to `configs/defaults.yaml`:
```yaml
runs:
  retention_days: 14
```
Local overrides may be added in `configs/local.yaml` (gitignored).

---

## 11) Risks & Mitigations
- **Disk bloat**: prune on save + optional cron.
- **Schema drift**: version `run_meta.schema_version` and provide migration shim.
- **Slate mismatch**: warn, allow “force load” with remap if player ID universe changed.

---

## 12) GitHub Actions (begin/end)
**Start:**
- Create branch: `feat/prp-runs-01`
- Open WIP PR targeting `dev`

**End:**
- Rebase on `dev`, squash-merge PR to `main` via integration
- Tag: `runs-01` (optional) and update `CHANGELOG.md`

---

## 13) Minimal Stubs (illustrative only)
```python
# src/runs/api.py
def save_run(slate_key: str, module: str, meta: dict) -> str: ...
def get_run(slate_key: str, module: str, run_id: str) -> dict: ...
def list_runs(slate_key: str, module: str, limit: int = 10) -> list[dict]: ...
def prune_runs(slate_key: str, module: str, retention_days: int = 14) -> int: ...
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
