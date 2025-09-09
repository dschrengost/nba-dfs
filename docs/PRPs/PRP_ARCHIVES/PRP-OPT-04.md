# PRP-OPT-04 — Optimizer Scaffold, Worker Setup, and Grid Rendering

**Owner:** Agent B  
**Repo:** `nba-dfs`  
**Scope:** Implement a pluggable optimizer scaffold that runs in a Web Worker, consumes normalized inputs, produces candidate lineups, and renders them in the grid. Results remain mock/simple but the pipeline and contracts are real.

---

## Deliverables
1) **Contracts & Types** — `OptimizerConfig`, `OptimizationRequest`, `OptimizationResult`, `Lineup`  
2) **Worker Runtime** — `workers/optimizer.worker.ts` + message protocol  
3) **Algorithm (placeholder)** — greedy/random-sample with salary/slot checks  
4) **UI Integration** — Run button in ControlsBar → orchestrator; render lineups in grid; Metrics drawer shows run summary  
5) **Error/Cancel** — cancel token, handle worker errors gracefully

---

## File Plan
```
lib/opt/types.ts
lib/opt/constraints.ts
lib/opt/algorithms/greedy.ts
workers/optimizer.worker.ts
lib/opt/run.ts
lib/state/run-store.ts
components/ui/ControlsBar.tsx
components/ui/LineupGrid.tsx
components/metrics/RunSummary.tsx
```

## Acceptance Criteria
- Clicking **Run** produces ≥ 50 candidate lineups quickly; UI stays responsive (worker).  
- Grid shows lineups; Metrics drawer shows run summary.  
- Cancel stops computation cleanly.  
- Contracts stable; swapping algorithm is trivial.

**Start:** `git checkout -b feature/optimizer-04` → PR → tag `v0.13.0`.
