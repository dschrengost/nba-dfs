# PRP: OPT-06C — RunSummary UX Polish, Lineup Table, & Dark Mode

## Summary
Polish the **RunSummary** page and lineup results UX. Replace the current card-only grid with a lightweight, high‑usability **Table view** (TanStack Table + shadcn/ui) while retaining the **Cards** view as a secondary option. Implement **site‑wide dark mode**. Ensure the optimizer emits and the UI displays **lineup‑level metrics** (names + IDs, dup risk, ownership/leverage aggregates, etc.). Add CSV export, sorting, column management, and Playwright coverage.

---

## GitHub actions (start of PR)
1. Create feature branch from `feature/opt-06c-ux-run`:
   - `git checkout -b feature/opt-06c-ux-run-ui-polish`
2. Open a draft PR (target: `feature/opt-06c-ux-run`), enable preview deploy.
3. Add CI job step for Playwright E2E (headless) on this PR.

---

## Scope
- **RunSummary polish** (metrics, badges, number formatting, skeletons).
- **Lineup Table view** with sorting, column visibility, pinning, search, CSV export, and optional virtualization for large runs.
- **Roster map** usage to show **player names + IDs** in each slot cell.
- **Dark mode** (site‑wide) with persistent theme toggle.
- **Optimizer data contract**: ensure all lineup‑level metrics needed by the table are emitted by backend and included in run `summary` payload.

### Out of scope
- New algorithms. (Only expose already‑computed metrics and light derivations.)
- Global navigation changes beyond theme toggle placement.

---

## Dependencies
- `@tanstack/react-table`
- `@tanstack/react-virtual` (only used if row count > ~1,500)
- `next-themes` (or equivalent) for theme persistence (matches shadcn docs)
- shadcn/ui components already in stack

---

## Design (shadcn + Tailwind)
### Layout
- Header: `Optimizer Run` + badges (Engine, λ, curve, drop%, uniques) using `Badge` + `Tooltip` + `Separator`.
- Two `Card`s for **Inputs / Outputs** and **Settings / Invalid reasons**. Consistent `dl` grids, `tabular-nums font-mono` for numbers, thousands separators, fallbacks `—`.
- **Tabs** or **ToggleGroup**: **Cards** | **Table**.
- Table resides inside a `Card` with `CardHeader` (toolbar) and `CardContent` (table).

### Table Toolbar
- Left: `Input` (search by player name/id), `DropdownMenu` (column show/hide & pinning).
- Right: `Button` (Export CSV), `Button` (Reset), small `Badge` for row count.
- Sticky header (`sticky top-0`), zebra rows, right‑aligned numeric columns.

### Player cells
- Two-line cell:
  - **Name** (truncate, tooltip full name + team/pos).
  - Small muted **(player_id)** with copy‑to‑clipboard icon button.
- If name missing, render ID prominently; tooltip: “name unavailable”.

### Dark mode
- Use shadcn recommended pattern with `next-themes` (`class` strategy).
- Global `<ThemeProvider>` in app root; theme toggle in header.
- Persist user choice; default to system. Ensure all `Card`, `Table`, `Badge`, `Tooltip` and borders read from CSS vars; avoid hardcoded colors.

---

## Data contract: lineup-level metrics
**Require optimizer to emit** the following per lineup. Add to payload `summary.lineups[]` OR `summary.results.lineups[]` (choose existing convention):

- `lineup_id`: string
- `score`: number
- `salary_used`: number
- `salary_left`: number (derived if not provided)
- **Slots**: `PG, SG, SF, PF, C, G, F, UTIL` as **player_id** strings
- `dup_risk`: number (0–1) if available
- Ownership / leverage aggregates (one or both):  
  - `own_sum` (or `own_avg`)  
  - `lev_sum` (or `lev_avg`)
- `num_uniques_in_pool`: number (vs pool baseline, if computed)
- `teams_used`: string[] or number (count); if array, UI shows count with tooltip list
- Optional: `proj_pts_sum`, `stack_flags` (e.g., “2-2”, “3-1”)
- **Roster map (separate object):** `playerMap: { [player_id: string]: { name: string; team?: string; pos?: string } }`

> UI must gracefully degrade if any field is absent; IDs always render.

---

## Deliverables (files)
- `components/metrics/RunSummary.tsx` — minor visual polish (badges wrap, number formatting, separators).
- `components/lineups/LineupTable.tsx` — TanStack headless table bound to shadcn `<Table>`.
- `components/lineups/LineupToolbar.tsx` — search, column chooser, export, reset.
- `hooks/useRosterMap.ts` — provides id→name map; accepts `summary.playerMap`; caches by slate/run.
- `lib/csv/exportLineups.ts` — exports **visible** columns with current sort/filter.
- `lib/table/columns.ts` — column defs, pinning support, `data-testid` hooks.
- `components/theme/ThemeToggle.tsx` — header control (icon button).
- App root provider for `ThemeProvider` (next-themes); small patch to layout.tsx/app.tsx.

---

## Acceptance Criteria
1. **Lineup Table view**
   - Sorting by **Score** (desc default), **Salary**, **Dup Risk**, **Uniques**.
   - Column visibility toggle & pinning; state persists per run in `localStorage`.
   - Player cells show **Name** + **(ID)**; copy‑ID button works.
   - Search filters rows by name or ID across all slots.
   - CSV export downloads current **visible** columns in current sort/filter order.
   - Sticky header; numeric columns are right‑aligned, `tabular-nums`.
   - Virtualization automatically activates when row count > 1,500 (no jank).

2. **RunSummary polish**
   - Inputs/Outputs and Settings render with consistent typography & spacing.
   - Numbers formatted: Score `x.xx`, Overlap `x.xx`, Jaccard `x.xxx`, ms with thousands separators.
   - All missing values show `—` and never break layout.

3. **Dark mode**
   - Theme toggle visible on the page; persists between visits.
   - All elements adapt to dark theme (no illegible text, borders visible).

4. **Optimizer data contract**
   - Payload includes all lineup-level metrics listed above, with `playerMap` present for the current slate/run. UI renders names where available.

5. **Playwright E2E**
   - Loads run → metrics visible, correctly formatted.
   - Table sorts by Score; user toggles Salary column off/on; pin a column; persists after reload.
   - Search for a **player_id** and **name** returns matching rows.
   - Export CSV → header order equals visible columns; row count matches filtered set.
   - Dark mode toggle flips palette; persists after reload.

6. **Performance & a11y**
   - Initial table render for 5,000 lineups < 500ms on dev M1; virtualized scrolling 60fps.
   - Axe checks pass for the page; keyboard focus visible for interactive elements.

---

## Test plan
- **Unit (Vitest):** CSV exporter, column def formatters, roster-map fallback logic.
- **Playwright:** scenarios in Acceptance Criteria §5 (headless + headed).
- **Snapshot:** dark & light themes for RunSummary cards and table header row.

---

## Implementation notes
- Keep existing **Cards** grid as a secondary tab.
- Prefer derived fields in UI if backend lacks them temporarily (e.g., compute `salary_left` client-side).
- Use `Intl.NumberFormat` for numeric formatting; avoid ad‑hoc `toFixed` where thousands separators are needed.
- Add `data-testid` across badges, metrics cells, toolbar controls.

---

## Risks / mitigations
- **Partial data:** Always show IDs; tooltips indicate missing names.  
- **Large datasets:** Turn on virtualization above threshold; avoid measuring DOM widths in loops.  
- **Theme drift:** Use CSS vars and shadcn tokens only; no hardcoded colors.

---

## GitHub actions (end of PR)
1. Rebase branch onto `feature/opt-06c-ux-run`; ensure green CI (unit + Playwright).
2. Squash & merge with message: `feat(ui): RunSummary polish, lineup table, dark mode, CSV export`.
3. Delete branch. Create follow‑up issue for any metrics still missing from optimizer payload.
