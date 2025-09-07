# PRP-OPT-06C (Update) — Full UX Run Controls & Wiring (wrapper-first)

**Branch**: `feature/opt-06c-ux-run`  
**Goal**: Expose **Penalty Curve** and **Drop Intensity** knobs in the UI, wire them through `run-store` → `/api/optimize` → Python wrapper, and verify via diagnostics.

---

## GitHub actions
- Start on `feature/opt-06c-ux-run`
- End: `git add -A && git commit -m "OPT-06C: expose penalty curve + drop intensity; complete UX run controls & metrics wiring"`

---

## Controls to expose (ControlsBar)
- **Number of lineups**: `N_lineups` (default 5, 1–150)
- **Ownership penalty**:
  - Toggle enable
  - **Lambda (λ)** numeric/slider (0–50, default 8)
  - **Penalty curve** select: `"linear"` → backend `"by_points"`; `"g_curve"` → backend `"g_curve"`
- **Drop intensity**: slider `0.00 … 0.50` (default `0.20`) → maps to **pruning** percentage
- **Randomness**:
  - Seed (int, default 42)
  - Sigma (σ) 0–0.25 (wire to `constraints.randomness_pct` as `σ*100`)
- **Paths**: `projectionsPath`, `playerIdsPath` (persist in `localStorage` under `dfs_paths`)

---

## IMPORTANT: Legacy naming for “Drop Intensity”
Legacy code refers to this feature as **pruning**. Expect fields like:
- `constraints.pruning.drop_pct` (input)
- Diagnostics: `diagnostics.pruning.enabled`, `original_players`, `kept_players`, `reduction_pct`, `top_pruned`

### Verify in repo (agent checklist)
Use ripgrep to confirm the legacy naming and where it’s consumed:
```bash
rg -n "prun|drop_pct|reduction_pct|kept_players|top_pruned" processes/optimizer/_legacy
```
If you see those diagnostics in prior runs, the backend is already honoring `pruning.drop_pct`.

---

## State & API payload

### `lib/state/run-store.ts` (new from 06C-revA) — extend run()
```ts
// lib/state/run-store.ts (excerpt)
async function runSolve({
  site,
  projectionsPath,
  playerIdsPath,
  nLineups,
  penaltyEnabled,
  lambdaVal,
  penaltyCurve,        // "linear" | "g_curve"
  dropIntensity,       // 0.0 - 0.5
  seed,
  sigma                // e.g., 0.07
}: RunInputs) {
  set({ loading: true });

  const ownership_penalty =
    penaltyEnabled
      ? { enabled: true,
          mode: penaltyCurve === "g_curve" ? "g_curve" : "by_points",
          weight_lambda: Number(lambdaVal) || 0 }
      : { enabled: false };

  const body = {
    site,
    enginePreferred: "cp_sat",
    constraints: {
      N_lineups: Number(nLineups) || 5,
      ownership_penalty,
      pruning: { drop_pct: Math.max(0, Math.min(0.5, Number(dropIntensity) || 0)) },
      randomness_pct: Math.round((Number(sigma) || 0) * 100),
    },
    seed: Number(seed) || 42,
    projectionsPath,
    playerIdsPath,
  };

  const res = await fetch("/api/optimize", { method: "POST", body: JSON.stringify(body) });
  const data = await res.json();

  const lineups = data.lineups ?? [];
  set({
    loading: false,
    lineups,
    summary: {
      ...data.summary,
      valid: lineups.length,
      tried: data.diagnostics?.N ?? data.summary?.tried ?? lineups.length,
      elapsedMs: data.summary?.elapsedMs
        ?? (data.diagnostics?.wall_time_sec ? Math.round(1000 * data.diagnostics.wall_time_sec) : undefined),
      bestScore: data.summary?.bestScore,
    },
    engineUsed: data.engineUsed ?? data.diagnostics?.engine,
    diagnostics: data.diagnostics,
  });

  // Toasts (pseudo hooks)
  if ((data.diagnostics?.matched_players ?? 100) < 90) toast.warn("Low DK ID match rate; check playerIdsPath");
  const ownMax =
    data.diagnostics?.normalization?.ownership?.max_after ??
    data.diagnostics?.normalization?.ownership?.own_max_after;
  if (ownership_penalty.enabled && (ownMax ?? 0) === 0) {
    toast.info("Ownerships are all 0; penalty has no effect");
  }
}
```

---

## ControlsBar wiring (sketch)
```ts
// components/ControlsBar.tsx (excerpt)
const [nLineups, setNLineups] = useState(5);
const [penaltyEnabled, setPenaltyEnabled] = useState(false);
const [lambdaVal, setLambdaVal] = useState(8);
const [penaltyCurve, setPenaltyCurve] = useState<"linear"|"g_curve">("linear");
const [dropIntensity, setDropIntensity] = useState(0.20);
const [seed, setSeed] = useState(42);
const [sigma, setSigma] = useState(0.07);
const [projectionsPath, setProjectionsPath] = useState("");
const [playerIdsPath, setPlayerIdsPath] = useState("");

useEffect(() => {
  const last = JSON.parse(localStorage.getItem("dfs_paths") ?? "{}");
  setProjectionsPath(last.projectionsPath ?? "");
  setPlayerIdsPath(last.playerIdsPath ?? "");
}, []);
useEffect(() => {
  localStorage.setItem("dfs_paths", JSON.stringify({ projectionsPath, playerIdsPath }));
}, [projectionsPath, playerIdsPath]);

const onRun = () =>
  runStore.getState().runSolve({
    site: "dk",
    projectionsPath,
    playerIdsPath,
    nLineups, penaltyEnabled, lambdaVal, penaltyCurve, dropIntensity,
    seed, sigma
  });
```

---

## RunSummary tweaks
- Valid lineups → `summary.valid`
- Candidates tried → `summary.tried`
- Best score → `summary.bestScore`
- Elapsed → `summary.elapsedMs`
- Engine → `engineUsed`
- Tag display (optional): `λ={diagnostics?.ownership_penalty?.lambda_used ?? constraints?.ownership_penalty?.weight_lambda}`, `curve={diagnostics?.ownership_penalty?.mode ?? "by_points"}`, `drop={(constraints?.pruning?.drop_pct ?? 0)*100}%`

---

## LineupsGrid (DK IDs)
```tsx
// components/LineupsGrid.tsx (excerpt)
<td title={`${p.name} (${p.pos}) — ${p.team} — $${p.salary} — own ${Math.round(100*(p.own_proj ?? 0))}%`}>
  {p.dk_id ?? "—"}
</td>
```

---

## Verification steps (agent must run)
1) **Legacy naming probe**:  
   ```bash
   rg -n "prun|drop_pct|reduction_pct|kept_players|top_pruned" processes/optimizer/_legacy
   ```
   Confirm we’re indeed using `pruning.drop_pct` and diagnostics surface reduction.

2) **API smoke** (g-curve + drop 0.20 + λ=8):  
   ```bash
   curl -sS -X POST http://localhost:3000/api/optimize      -H 'Content-Type: application/json'      -d '{
       "site":"dk",
       "enginePreferred":"cp_sat",
       "constraints":{
         "N_lineups":5,
         "ownership_penalty":{"enabled":true,"mode":"g_curve","lambda":8},
         "pruning":{"drop_pct":0.2}
       },
       "seed":42,
       "projectionsPath":"tests/fixtures/dk/2024-01-15/projections.csv",
       "playerIdsPath":"tests/fixtures/dk/2024-01-15/player_ids.csv"
     }' | jq '.ok, .diagnostics.ownership_penalty.mode, .diagnostics.pruning.enabled, .diagnostics.pruning.reduction_pct'
   # expect: true, "g_curve", true, > 0
   ```

3) **UI run**: set knobs in ControlsBar; expect Valid=5, Engine=CP-SAT, DK IDs visible; toasts when appropriate.

---

## Rollback
- Revert changes in `ControlsBar.tsx`, `RunSummary.tsx`, `LineupsGrid.tsx`, `lib/state/run-store.ts`, `lib/opt/run.ts`.
- Clear localStorage key `dfs_paths`.
