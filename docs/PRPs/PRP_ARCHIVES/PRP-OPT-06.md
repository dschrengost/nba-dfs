
# PRP-OPT-06 — Integrate Legacy Optimizer w/ New Pipeline (CP‑SAT by default)

**Owner:** Optimizer Agent  
**Status:** Proposed  
**Branches:** `feature/opt-06-integrate-cpsat`  
**Timebox:** 1–2 focused sessions

---

## Why
Our UI currently runs a JS prototype (greedy). We want **true solver** results and feature parity with the legacy engine. This PRP cleanly integrates `processes/optimizer/_legacy/nba_optimizer_functional.py` into the new pipeline and makes **CP‑SAT the default**, with CBC as a safe fallback.

---

## Outcomes
- ControlsBar knobs drive a **single contract** passed to a solver backend.
- Web Worker invokes **Python optimizer** instead of the TS greedy prototype.
- **CP‑SAT** is default (if OR‑Tools present); **CBC** fallback otherwise.
- Ingested CSVs (or fallback fixtures) feed the solver; **lineups > 0** on DK fixture.
- Summary shows **engine used**, options used, invalid‑reason counts, and ownership telemetry when enabled.

---

## Scope (what changes)
### Backend bridge
- Add a **CLI shim** that reads JSON on stdin and returns JSON on stdout:
  - `scripts/pyopt/optimize_cli.py`
  - Calls `nba_optimizer_functional.optimize_with_diagnostics(...)`.
  - Selects engine: `cp_sat` (preferred) → `cbc` (fallback) if OR‑Tools unavailable.
  - Normalizes ownership to `[0,1]` and carries diagnostics.
- Use **uv** for Python deps (repo preference):
  - `uv.lock` / `pyproject.toml` add: `pulp`, `ortools`, `pandas`, `numpy`, `fastjsonschema` (optional), `click` (optional).

### Node orchestration
- Update **runner** to spawn the Python CLI via `uv`:
  - File: `lib/opt/run.ts`
  - Replace/branch the current worker path: use **subprocess** to `uv run python scripts/pyopt/optimize_cli.py` with a JSON payload derived from run‑store state.
  - Keep the current Web Worker as an **optional “local sampler”** fallback (flag‑controlled) to avoid blocking if Python is misconfigured.
- Extend **types** to include solver engine + diagnostics echo:
  - `lib/opt/types.ts` adds `engineUsed: "cp_sat" | "cbc"`, `diagnostics?: unknown` on summary.

### Ingest contract
- Reuse ingested canonical schema (zero‑drop DK join).
- Adapter in CLI shim converts canonical JSON → Pandas DF expected by the legacy optimizer (columns: `name, team, position, salary, proj_fp, own_proj?, dk_id?`).

### UI
- No layout changes. ControlsBar and Metrics drawer already show options + reasons.
- Add a small badge in `RunSummary` for **Engine: CP‑SAT/CBC** based on `engineUsed`.

---

## Out of scope
- Server mode (FastAPI/Flask). We use a **CLI subprocess** for simplicity.
- Multi‑game slates logic changes (positions/constraints remain as in legacy file).
- New knobs beyond the ones already surfaced.

---

## Contracts

### Request → Python (stdin JSON)
```jsonc
{
  "site": "dk",
  "enginePreferred": "cp_sat",     // "cp_sat" | "cbc"
  "constraints": { /* existing TS constraints, incl. salary, team cap, uniques, N_lineups, ownershipPenalty */ },
  "players": [
    {
      "player_id": "123",
      "name": "Player Name",
      "team": "PHX",
      "position": "PG/SG",
      "salary": 7200,
      "proj_fp": 34.5,
      "own_proj": 0.12,            // optional, 0..1
      "dk_id": "9876543"           // optional
    }
  ],
  "seed": 42
}
```

### Response ← Python (stdout JSON)
```jsonc
{
  "ok": true,
  "engineUsed": "cp_sat",
  "lineups": [
    {
      "lineup_id": 1,
      "total_proj": 297.4,
      "total_salary": 49800,
      "players": [
        {"player_id":"123","name":"...","pos":"PG","team":"PHX","salary":7200,"proj":34.5,"dk_id":"9876543","own_proj":0.12}
        // 8 DK slots
      ]
    }
  ],
  "summary": {
    "tried": 1, "valid": 1, "bestScore": 297.4, "elapsedMs": 420,
    "invalidReasons": {"salary":0,"slots":0,"teamcap":0,"dup":0},
    "optionsUsed": {/* echo of knobs */}
  },
  "diagnostics": { /* pass-through from optimizer_with_diagnostics */ }
}
```

---

## Tasks

### T0 — Branch & guardrails
- Create: `feature/opt-06-integrate-cpsat`.
- Add a **runtime toggle** (env var `DFS_SOLVER_MODE=python|sampler`) default `python`.

### T1 — Python CLI shim
- Add `scripts/pyopt/optimize_cli.py`:
  - Parse stdin JSON, create Pandas DF, call `optimize_with_diagnostics`.
  - Detect OR‑Tools availability: prefer `"cp_sat"`, else `"cbc"`.
  - Emit the response JSON to stdout (no logs on stdout; logs → stderr).

### T2 — Node runner wiring
- Update `lib/opt/run.ts`:
  - If mode `python`, spawn CLI using `child_process.spawn`:
    - command: `uv`
    - args: `["run", "python", "scripts/pyopt/optimize_cli.py"]`
    - stream stdin, collect stdout; map to existing `RunSummary` shape.
  - On spawn error/non‑zero exit: surface a clear UI error and suggest installing Python/uv/ortools.
  - Keep current Worker sampler under a flag (`DFS_SOLVER_MODE=sampler`).

### T3 — Types & UI
- `lib/opt/types.ts`: extend summary with `engineUsed` and `diagnostics` (opaque).
- `components/metrics/RunSummary.tsx`: show `Engine: CP‑SAT` or `CBC`.
- No other UI changes.

### T4 — QA & docs
- Fixture QA: run with `fixtures/dk/2024-01-15/mergedPlayers.json` → **valid > 0**.
- Upload QA: drag in your known 116‑player CSVs → **valid > 0** under default knobs.
- Add `README.md` snippet: installing Python/uv/ortools; env toggle; troubleshooting.

---

## File diffs (planned)
- **NEW** `scripts/pyopt/optimize_cli.py`
- **MOD** `lib/opt/run.ts` (spawn Python, map results)
- **MOD** `lib/opt/types.ts` (engineUsed/diagnostics)
- **MOD** `components/metrics/RunSummary.tsx` (engine badge)
- **NEW** `pyproject.toml`, `uv.lock` (deps: `ortools`, `pulp`, `pandas`, `numpy`)
- **DOC** `docs/PRPs/PRP-OPT-06.md` (this file)
- **DOC** `README.md` (short how‑to)

---

## Acceptance criteria
- With fixture (116 players), default knobs → **valid lineups > 0**.
- With uploaded DK CSVs (players + projections), strict join holds and solver returns lineups.
- Summary shows **engineUsed=cp_sat** when OR‑Tools present; **cbc** when not.
- No UI freezes; errors are user‑friendly (missing Python/uv/ortools).

---

## Local runbook
```bash
# (once) install uv & python 3.11+
# macOS: pipx install uv  OR  brew install uv

# python deps
uv sync

# dev
npm run dev
# ensure DFS_SOLVER_MODE=python (default)
# Optimizer → Run
```

---

## Git actions

### Start
```bash
git checkout -b feature/opt-06-integrate-cpsat
git add docs/PRPs/PRP-OPT-06.md
git commit -m "docs: add PRP-OPT-06 (optimizer integration; CP-SAT default)"
git push -u origin feature/opt-06-integrate-cpsat
```

### End (after implementation)
```bash
# open PR
gh pr create -B main -H feature/opt-06-integrate-cpsat   -t "PRP-OPT-06: integrate legacy optimizer via CLI (CP-SAT default)"   -b "Wire UI → Node runner → Python CLI → nba_optimizer_functional (CP‑SAT default; CBC fallback)."

# merge (squash)
gh pr merge --squash --delete-branch
git pull
```
