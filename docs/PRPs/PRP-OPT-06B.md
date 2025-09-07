# PRP-OPT-06B — Native TypeScript Solver (CP‑SAT default, CBC fallback)

**Goal**: Remove the Python bridge for production paths by implementing a native TypeScript optimizer pipeline that slots into existing UI/worker/state with no further UI changes. Keep CP‑SAT as default, CBC as fallback, preserve ownership penalty + randomness, and align with our house ingest schema.

---

## GitHub actions

**Start**
- Branch: `feature/opt-06-integrate-cpsat` (continue)
- Scope: TS-only solver modules + wiring + tests; do **not** remove Python yet

**End**
- `git add` changed files
- `git commit -m "OPT-06B: native TS solver (CP‑SAT default, CBC fallback) + wiring + tests"`
- No push/PR (local per instructions)

---

## Scope / Non‑Goals
**In**: CP‑SAT implementation, CBC fallback, schema translation, penalty/randomness parity, worker integration, tests, docs.  
**Out**: Removing Python CLI entirely (keep until OPT‑06C), advanced solver features (groups/stacking exposure caps beyond existing), slate download/ETL changes.

---

## Module layout (new/changed)

```
lib/opt/
  solver.ts              # interface + shared types (NEW)
  cpsat.ts               # CP‑SAT impl (NEW)
  cbc.ts                 # CBC impl (NEW)
  translate.ts           # house schema → model vars/constraints (NEW)
  run.ts                 # add router: ts-cpsat | ts-cbc | python (UPDATE)
workers/optimizer.worker.ts   # thread TS solver (UPDATE)
lib/state/run-store.ts        # capture engineUsed, diagnostics (UPDATE)
lib/opt/types.ts              # extend RunSummary/diagnostics if needed (UPDATE)
README.md                     # usage + env (UPDATE)
```

---

## Key design

### 1) Solver interface (thin & stable)
```ts
// lib/opt/solver.ts
export type Engine = "cp_sat" | "cbc";
export interface SolveParams {
  site: "dk" | "fd";
  seed: number;
  constraints: {
    N_lineups: number;
    unique_players?: number;
    max_salary?: number;
    min_salary?: number;
    global_team_limit?: number;
    team_limits?: Record<string, number>;
    lock_ids?: string[];
    ban_ids?: string[];
    ownership_penalty?: { enabled: boolean; mode?: "by_points"; weight_lambda?: number };
    randomness_pct?: number; // 0–100; deterministic w/ seed
  };
}
export interface PlayerIn {
  name: string; team: string; position: string; salary: number;
  proj_fp: number; own_proj?: number | null; dk_id?: string | null; player_id?: string | null;
}
export interface LineupOut {
  lineup_id: number; total_proj: number; total_salary: number;
  players: Array<{ player_id?: string; name: string; pos: string; team: string; salary: number; proj: number; dk_id?: string | null; own_proj?: number | null; }>;
}
export interface Diagnostics {
  engine: Engine; status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR";
  wall_time_ms?: number; model?: Record<string, number>; params?: Record<string, unknown>;
  normalization?: { ownership?: Record<string, unknown> };
  ownership_penalty?: { enabled: boolean; lambda_used: number; applied: boolean; avg_chalk_index?: number; avg_penalty_points?: number; };
}
export interface Solver {
  name: Engine;
  solve(players: PlayerIn[], p: SolveParams): Promise<{ lineups: LineupOut[]; diagnostics: Diagnostics }>;
}
```

### 2) Translation (schema → model)
- Validate positions (DK 8-slot spec) and salary cap.
- Normalize ownership to [0,1].
- Pre-prune pool (e.g., low‑proj punts) with same heuristic we used in legacy diagnostics.
- Deterministic RNG via `seedrandom` for randomness_pct.

### 3) CP‑SAT default (Node OR‑Tools)
- Use `@google/ortools` CP‑SAT (int var per (player,slot), salary sum constraint, team caps, uniqueness).
- Objective: `sum(points) − λ * sum(own_proj)` (scaled integer, e.g., ×1000).
- Parameters: set time limits, threads, random seed.

### 4) CBC fallback
- Use a small ILP builder (e.g., `glpk.js` or CBC via a thin binding). Same constraints/objective, same scaling.

### 5) Routing & UX
- `lib/opt/run.ts` recognizes `DFS_SOLVER_MODE=ts` (default), `ts-cpsat`, `ts-cbc`, and `python` for parity testing.
- `RunSummary` shows engineUsed + key timings; no UI changes needed.

---

## Implementation plan (bite‑size steps)

1. **Interfaces** — add `lib/opt/solver.ts` & `lib/opt/types` bumps.  
2. **Translator** — `lib/opt/translate.ts` (schema checks, scaling, RNG).  
3. **CP‑SAT impl** — `lib/opt/cpsat.ts` (build model, objective, run solver, collect diag).  
4. **CBC impl** — `lib/opt/cbc.ts` (parity objective/constraints).  
5. **Router** — update `lib/opt/run.ts` to select engine; add env toggles.  
6. **Worker wiring** — `workers/optimizer.worker.ts` to call TS solver; error guard.  
7. **State/summary** — ensure diagnostics surface.  
8. **Tests** — unit (translator, constraint math), golden (seeded slates), parity vs CLI bridge.  
9. **Docs** — README: modes, env, troubleshooting.

---

## Tests (minimal but meaningful)

### Unit
- translate: salary cap respected; team caps; uniqueness; ownership normalization.
- penalty: with λ>0 and non‑flat ownership, penalty reduces objective vs λ=0.
- randomness: fixed seed → identical outcomes.

### Golden (seeded)
- Fixture `tests/fixtures/dk/2024-01-15/`: run TS CP‑SAT with λ=8 → compare total_proj deltas within tolerance vs Python CP‑SAT.

### Integration smoke
```bash
# TS CP‑SAT (default)
NEXT_PUBLIC_DFS_SOLVER_MODE=ts npm run dev
# trigger run from UI; expect Engine badge “CP‑SAT” and valid DK IDs

# Direct worker harness (if present)
node scripts/dev/run-ts-solver.mjs fixtures/dk/2024-01-15/projections.csv --playerIds tests/fixtures/dk/2024-01-15/player_ids.csv --lambda 8 --seed 42
```

---

## Acceptance
- TS CP‑SAT returns N lineups with valid DK IDs (from existing ingest path).
- Ownership penalty applied (`lambda_used > 0`, non‑zero penalty points) when inputs have non‑flat ownership.
- Randomness deterministic with seed.
- CBC fallback selectable and functional.
- UI unchanged; `RunSummary` shows engine + timings; worker path stable.
- Parity: For fixed seed, TS vs Python top lineup total within small tolerance (≤0.5 FP) on fixture slate.

---

## Notes / deps
- Add `@google/ortools` and `seedrandom`. Keep sizes small; lazy‑load solver module inside worker to avoid main bundle bloat.
- Keep Python CLI behind `DFS_SOLVER_MODE=python` for parity testing until OPT‑06C.

---

## Rollback
- `git restore` changed files in `lib/opt/*`, worker, state, README; set `DFS_SOLVER_MODE=python` to revert to bridge.

---

## Tiny code stubs (reference only; keep diffs small)
```ts
// lib/opt/run.ts (router sketch)
const MODE = process.env.NEXT_PUBLIC_DFS_SOLVER_MODE ?? process.env.DFS_SOLVER_MODE ?? "ts";
export async function runSolve(req) {
  if (MODE === "python") return callPythonApi(req);
  const engine = MODE === "ts-cbc" ? "cbc" : "cp_sat";
  const solver = engine === "cp_sat" ? await import("./cpsat") : await import("./cbc");
  return solver.solve(req.players, { site: req.site, seed: req.seed, constraints: req.constraints });
}
```
