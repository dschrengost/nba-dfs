# PRP-OPT-05 — Expose Optimizer Knobs (from legacy) & Deprecate DK‑Strict

**Owner:** Agent B  
**Repo:** `nba-dfs`  
**Goal:** Expose the key **optimizer controls** in the new Next.js UI (ControlsBar) and wire them through **run → worker → algo**, using the knobs proven in the legacy `processes/optimizer/_legacy/optimize.py`. Deprecate the old **DK‑Strict** toggle (no-op shim) so there is a single modern path.

---

## Why
Legacy Streamlit UI (`optimize.py`) already defines practical knobs (seed, candidates/lineups, salary limits, team cap, randomness, ownership penalty, engine presets). The new shell currently has a **Run** button with defaults only; users can’t tune constraints and we still see **Valid lineups = 0** in some cases because constraints aren’t adjustable. This PRP ports the **controls and their plumbing** into the modern app.

---

## Scope (What to Implement Now)

### UI Controls (ControlsBar)
Expose as simple inputs (dev-styled OK; shadcn components):
- **Candidates** (int, default 20_000) — how many candidates to try in the sampler.
- **Team cap** (int, default 3) — max players per team (0 disables).
- **Salary cap** (int, default 50_000) — DK cap (keep default).
- **Min salary** (int, default 0 / optional) — allow “leave salary on table”.
- **Seed** (text, default deterministic) — affects sampler order.
- **Randomness %** (0–100, default 0) — optional variance to projections (kept but can be pass‑through now).
- **Ownership penalty (toggle)** — pass‑through to worker (implementation may be a no‑op initially; just plumb it).

> Out of scope for this PRP: engine selection (CP‑SAT/CBC), strict solver presets, and the full ownership penalty curve UI. Those can be a follow‑up PRP.

### Wiring
- Thread a single `options` object from **ControlsBar → useRunStore.run(options) → lib/opt/run.ts → worker**.
- Default to values from **lib/opt/config.ts** when a field is empty; persist last‑used values in store (session only).

### Worker/Algo
- Worker accepts the options, merges with defaults, and passes into the sampler (`lib/opt/algorithms/greedy.ts`).
- Add constraint checks in the validator (salary ≤ cap, 8 DK slots, team cap); return **reasons** counters: `{salary, slots, teamcap, dup}` into diagnostics.
- Respect **min salary** (i.e., `total_salary >= min_salary` when set).
- Apply `randomness_pct` as **optional noise** to projections (uniform ±X% around proj) behind a flag.

### Metrics/UX
- **RunSummary** shows the knobs echo (seed, candidates, team cap, caps), and a small breakdown: `invalid reasons: {salary, slots, teamcap, dup}`.
- Keep determinism: same seed + data + knobs → same result.

### Deprecate DK‑Strict
- Remove the toggle from our modern path; if any code still branches on it, make it a **no‑op** and mark with `@deprecated` comment. (Legacy file remains untouched.)

---

## Files to Touch

- `components/ui/ControlsBar.tsx` — add inputs, local state, call `run(options)`.
- `lib/state/run-store.ts` — update `run(options)` signature; store last‑used knobs.
- `lib/opt/config.ts` — centralize defaults (`CANDIDATES`, `TEAM_CAP`, `SALARY_CAP`, `MIN_SALARY`, `SEED`, `RANDOMNESS_PCT`).
- `lib/opt/run.ts` — merge knobs + data, post to worker, plumb diagnostics back.
- `workers/optimizer.worker.ts` — accept options, count invalid reasons, post progress + final summary.
- `lib/opt/algorithms/greedy.ts` — ensure validator honors all constraints; support min salary and team cap properly; use UTIL/G/F flex correctly.
- `components/metrics/RunSummary.tsx` — display knob echo + invalid reasons.
- (Optional) `lib/opt/types.ts` — define `RunOptions` type.

---

## Acceptance Criteria

- UI shows **Candidates, Team cap, Salary cap, Min salary, Seed, Randomness %, Ownership toggle**.
- Clicking **Run** with defaults yields **Valid lineups > 0** on the 2024‑01‑15 fixture and on live ingest.
- **RunSummary** includes an “invalid reasons” breakdown and echoes the knobs used.
- Re‑running with identical seed/knobs/data yields identical best lineup (deterministic).
- No references to DK‑Strict toggle in the modern path (kept as deprecated comment only).

---

## Out of Scope (follow‑ups)
- Full **ownership penalty UI** (curves, pivots) and solver engine selection.
- Animated tab underline/polish and adopt Aceternity effects.
- Persist knobs across sessions (localStorage) — optional later.

---

## Risks & Mitigations
- **Too many invalids** → expose reasons counters to tune team cap/candidates quickly.
- **Noise changes ranking** → keep randomness off by default; gate behind opt‑in toggle.
- **DK‑Strict removal** → leave legacy path untouched; just deprecate in modern code.

---

## Branch & PR

- Start: `git checkout -b feature/optimizer-05-knobs`
- PR Title: **PRP-OPT-05: Expose optimizer knobs & deprecate DK‑Strict**
- Tag after merge (optional): `v0.14.0`

---

## Agent Kickoff — One‑liner

Read `docs/PRPs/PRP-OPT-05.md`. On branch `feature/optimizer-05-knobs`, add UI inputs (candidates, team cap, salary/min salary, seed, randomness %, ownership toggle) to `ControlsBar`, thread an `options` object through `run-store → run.ts → optimizer.worker → greedy.ts`, honor constraints (including min salary), return invalid reason counts, echo settings in `RunSummary`, and deprecate DK‑Strict in the modern path. Open a PR when **Valid lineups > 0** on the DK fixture and the reasons breakdown renders.
