# PRP-OPT-04A — Real DK Fixtures & Deterministic Test Harness

**Owner:** Agent B  
**Repo:** `nba-dfs`  
**Purpose:** Use *real DraftKings* CSVs (your `projections.csv` + `player_ids.csv` from a past date) as fixtures so the optimizer scaffold (PRP-OPT-04) is tested with realistic data. Keep ingestion optional: if PRP-INGEST-03 isn’t merged, use a temporary normalizer to make a snapshot the worker can consume.

---

## Why
Running the optimizer against real DK-shaped data surfaces constraints/edge-cases early (positions, salary caps, duplicate IDs, missing aliases) and proves the worker + UI remain responsive under realistic sizes.

---

## Inputs (provided by you)
Place your historical files here (adjust date as needed):
```
fixtures/dk/2024-01-15/projections.csv
fixtures/dk/2024-01-15/player_ids.csv
```
> Use any "random date from last year" you choose. The path date is only for organization.

---

## Deliverables

1) **Fixtures**
- Add your two CSVs under `fixtures/dk/<DATE>/` (kept in Git so agents can run deterministically).

2) **Normalization Snapshot**
- If PRP-INGEST-03 is **available**: run its normalizer to produce a stable JSON snapshot:
  ```
  fixtures/dk/<DATE>/mergedPlayers.json   # output: MergedPlayer[]
  ```
- If PRP-INGEST-03 is **not yet merged**: implement a tiny, local **bridge normalizer** (no network) that:
  - Applies a minimal alias map (e.g., `proj, proj_pts` → `proj_pts`)
  - Coerces numbers (salary, proj_pts)
  - Joins on `player_id`
  - Writes `mergedPlayers.json`

3) **Optimizer Wiring**
- Optimizer runner **prefers live ingest store** when present.
- If store is empty, it **falls back** to loading `fixtures/dk/<DATE>/mergedPlayers.json`.
- Add a deterministic `seed` default (e.g., `"dk-fixture-<DATE>"`).

4) **Config toggles**
- Add `lib/opt/config.ts`:
  - `DEFAULT_FIXTURE_DATE = "<DATE>"`
  - `USE_FIXTURE_FALLBACK = true` (until PRP-INGEST-03 lands)
  - `DEFAULT_SALARY_CAP = 50000`, `ROSTER_SLOTS` per DK

5) **QA Harness**
- Script/command to run the worker with the fixture (no UI) and print summary counts:
  - candidates tried, valid lineups, best score, time elapsed

---

## File/Module Plan
```
fixtures/dk/<DATE>/projections.csv
fixtures/dk/<DATE>/player_ids.csv
fixtures/dk/<DATE>/mergedPlayers.json     # generated

lib/opt/config.ts                         # defaults (cap, slots, fixture date, seed)
lib/opt/fixtures.ts                       # load snapshot or fail gracefully
lib/opt/run.ts                            # prefer store; else fallback to fixtures
scripts/make-fixture-snapshot.ts          # bridge normalizer if ingest not merged (node script)
components/metrics/RunSummary.tsx         # include "Fixture: <DATE>" when using fallback
```

---

## Acceptance Criteria
- With only the two CSVs added under `fixtures/dk/<DATE>/`, the project:
  - **Generates** `mergedPlayers.json` (via ingest or bridge normalizer).
  - **Runs** optimizer worker and renders ≥ 50 candidate lineups through the UI grid.
  - **Deterministic** results for the same seed (best lineup score stable across runs).
  - **Responsive UI** (no blocking) during the run.
- When PRP-INGEST-03 is merged, toggling `USE_FIXTURE_FALLBACK=false` makes the optimizer use live ingested data instead of the snapshot.

---

## Notes & Guardrails
- Keep the bridge normalizer small and testable; once PRP-INGEST-03 is in, delete it and use the real ingest pipeline.
- Do **not** add any network calls.
- Size guardrails: the UI must remain responsive with 10–30k rows merged.

---

## Agent Tasks

**T0 — Plan (no writes)**  
- Confirm fixture paths and selected date; list alias assumptions for projections file.

**T1 — Fixture Loader + Config**  
- Add `lib/opt/config.ts` and `lib/opt/fixtures.ts`; load JSON snapshot and surface via a typed function.

**T2 — Bridge Normalizer (temporary if needed)**  
- Node script to parse the two CSVs, apply alias map, coerce numeric fields, join on `player_id`, write `mergedPlayers.json`.

**T3 — Optimizer Fallback**  
- In `lib/opt/run.ts`, prefer store; else load `fixtures` snapshot and proceed.

**T4 — QA Harness**  
- Add a simple CLI script to run the worker with the snapshot and log summary; document command in README.

**T5 — UI Badge**  
- When using fixtures, show a small "Fixture: <DATE>" badge in RunSummary.

---

## Branch & PR
**Start:** `git checkout -b feature/optimizer-04-fixtures`  
**End:** `gh pr create -t "PRP-OPT-04A: Real DK fixtures & deterministic harness" -b "Adds dk/<DATE> fixtures, snapshot, fallback, seed, and QA harness"`

