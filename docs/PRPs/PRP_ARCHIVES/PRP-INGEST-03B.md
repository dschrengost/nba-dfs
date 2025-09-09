# PRP-INGEST-03B — DK Header Aliases & Zero‑Drop Normalization (ALL players must match)

**Owner:** Agent A  
**Repo:** `nba-dfs`  
**Goal:** Make ingest accept **real DraftKings CSVs** and produce a **canonical, fully‑joined** `MergedPlayer[]` with **zero drops** (every player row in `player_ids.csv` must match a projections row, and vice‑versa). Replace the current behavior where all rows were dropped due to header mismatches.

---

## Requirements (non‑negotiable)

- **Zero‑drop join**: `merged_count == players_count == projections_count`. If mismatches remain, treat them as **errors to fix**, not “informational.”
- **No network calls.**
- **Deterministic output**: same input → same `MergedPlayer[]` order + values.
- **Performance**: handle 10–30k rows without jank in the UI (streaming parse + yielding).

---

## Canonical Model (unchanged)

We keep a single **canonical schema** for the pipeline and map vendor fields into it.

```ts
// lib/domain/types.ts (already present; reference only)
type Player = {
  player_id: string;            // DK id preferred
  name: string;                 // "FIRST LAST"
  team: string;                 // BOS, LAL, ...
  pos: string[];                // ["PG","SG"]
};

type Projection = {
  player_id?: string;
  name: string;
  team?: string;
  pos?: string[];
  salary?: number;              // DK salary (int)
  proj_pts: number;             // required
  proj_sd?: number;
  own_pct?: number;
  field_pts?: number;
};

type MergedPlayer = Player & Projection;  // union of canonical fields
```

---

## Header Alias Map (DK → Canonical)

Apply **before** validation. Trim header text, drop BOM, collapse spaces.

### `player_ids.csv` (DK Players)
| DK Header      | Canonical  | Notes |
|---|---|---|
| `ID` or `Player ID` | `player_id` | prefer numeric/string id |
| `Name`        | `name`     | normalize diacritics & whitespace |
| `Position`    | `pos`      | split on `/` → array |
| `TeamAbbrev`  | `team`     | 3‑letter |
| `Game Info`   | `game`     | optional passthrough |

### `projections.csv` (DK Projections)
| DK Header  | Canonical   | Notes |
|---|---|---|
| `Name`     | `name`      | |
| `Position` | `pos`       | split on `/` |
| `Team`     | `team`      | 3‑letter |
| `Salary`   | `salary`    | int |
| `FPTS`     | `proj_pts`  | required number |
| `StdDev`   | `proj_sd`   | number optional |
| `Own%`     | `own_pct`   | number optional (strip `%`) |
| `FieldFpts`| `field_pts` | number optional |

> Keep schema **canonical** in Zod; only the **adapter** mutates header names.

---

## Coercions & Normalization

- Trim strings; collapse internal whitespace; strip BOM.
- **Numbers**: `salary`, `proj_pts`, `proj_sd`, `own_pct`, `field_pts` via safe coercion (`Number`, remove `%`, commas).
- **Positions**: `"PG/SF"` → `["PG","SF"]` (uppercased, deduped).
- **Name key**: uppercase, remove periods, extra spaces (`"Jr."` → `"JR"`). Keep original `name` for UI; use normalized for matching.
- **Teams**: uppercased; allow simple alias set (`NO`↔`NOP`, `PHO`↔`PHX`, `SA`↔`SAS`) in a tiny map.

---

## Join Strategy (strict, zero‑drop)

1. **Primary**: join on `player_id` if present in both.
2. **Secondary**: fallback to **name+team+primaryPos** composite key after normalization.
3. **Tertiary (last‑mile fixes)**: small **manual alias map** for known DK quirks (e.g., team code renames or middle‑initial variants). Keep this map in `lib/ingest/aliases.ts` with unit tests.

If any player still fails to join, **fail the ingest** with a precise error list and counts (do not silently pass with drops).

---

## Implementation Plan

**T0 — Plan (no writes)**  
- Confirm column presence in your real CSVs; list extra columns to ignore.

**T1 — Adapter Layer**  
- `lib/ingest/adapter.ts`: header rename + value coercions (per tables above).

**T2 — Schemas (Zod)**  
- Keep canonical Zod schemas; allow unknown keys (`.passthrough()`), and validate **after** adapter.

**T3 — Parser**  
- `lib/ingest/parse.ts`: Papaparse streaming; yield to UI between chunks.

**T4 — Normalizer + Join**  
- `lib/ingest/normalize.ts`: build maps for `player_id` and composite key; perform strict join; assemble `MergedPlayer[]`.

**T5 — Store + Summary**  
- `lib/state/ingest-store.ts`: store merged, counts; **error if counts don’t match**.  
- `components/metrics/IngestSummary.tsx`: show **players_count**, **projections_count**, **merged_count** and **0 unknown/0 dropped**. If non‑zero, render error panel listing offenders.

**T6 — Fixtures Snapshot**  
- Regenerate `fixtures/dk/<DATE>/mergedPlayers.json` from real files once join is 100% complete.

**T7 — Tests**  
- Unit tests for adapter coercions, alias map, strict join behavior, and error surface (jest/vitest).  
- Snapshot test for a small synthetic DK pair (3–5 players) that covers edge cases.

---

## Acceptance Criteria

- Metrics drawer shows **Players = Projections = Merged**, with **0 dropped**, **0 unknown**.  
- Optimizer **Run** produces valid lineups using the merged data (with fixture badge when fallback is used).  
- `scripts/make-fixture-snapshot.mjs <DATE>` writes a stable JSON used by the fixture loader.  
- Large files (10–30k rows) ingest without freezing the UI.

---

## Branch & PR

- **Start:** `git checkout -b feature/ingest-03b-dk-zero-drop`  
- **End:** PR title: **“PRP-INGEST-03B: DK aliases & zero‑drop normalization (strict join)”**  
- Include: before/after Metrics screenshots; counts proving full match.

---

## Agent One‑Liner (kickoff)

> Read `docs/PRPs/PRP-INGEST-03.md` and `docs/PRPs/PRP-INGEST-03B.md`. On branch `feature/ingest-03b-dk-zero-drop`, implement a header adapter for DK files, canonical Zod validation, strict zero‑drop join with id→composite fallback, and updated metrics summary. Regenerate `fixtures/dk/<DATE>/mergedPlayers.json`. Open PR when merged_count equals players_count equals projections_count.
