# PRP-FS-06 — Field Sampler Page

## 1. Goal
Deliver the Field Sampler page that mirrors the Optimizer and Variant Builder UX while generating a public contest field and injecting our Variant Catalog after generation. The page must surface field metrics, allow configuration of sampling knobs, and integrate with the unified data pipeline.

---

## 2. UX Layout

1. **Page Container & States**
   - Reuse `PageContainer` grid scaffold used by Optimizer and Variants pages so the Field page inherits `empty → loading → loaded` states【F:app/(studio)/field/page.tsx†L1-L20】【F:app/(studio)/optimizer/page.tsx†L1-L26】.
   - Default state: `empty` (no run yet). On "Run Field" click → `loading` (skeleton grid) → `loaded` (lineup views).

2. **Configuration Panel**
   - **Contest Settings**: `total_entries`, `seed`, `salary_cap`, `max_per_team`, ownership curve, diversity/de-dup toggles (map to `field_size`, `team_limits`, `ownership_curve`, `de-dup`, `seed` knobs from adapter).
   - **Variant Catalog Injection**: dropdown listing recent variant runs via `/api/runs?module=variants`.
   - Display computed `base_field_size = total_entries - variant_catalog_count` inline so users see how many public lineups will be generated.

3. **Run Controls & Summary**
   - Primary "Run Field" button, secondary "Reset".
   - Summary bar after completion showing: `run_id`, `field_base_count`, `injected_count`, `duplication_risk`, link to underlying variant run.

4. **Lineup Views**
   - Reuse `LineupViews` component so cards/table tabs match Optimizer UX【F:components/lineups/LineupViews.tsx†L1-L120】.
   - Extend table columns to include `source` (public/injected) in addition to existing metrics (`lineup_id`, `score`, `salary_used`, `own_avg`, `num_uniques_in_pool`, players by DK slot, etc.)【F:lib/table/columns.tsx†L7-L31】.

---

## 3. Backend & Data Wiring

1. **POST `/api/field`**
   - Accept: `{ slateId, totalEntries, seed, config, injectRun? }`.
   - Resolve selected variant run (if any) via `injectRun` → load `variant_catalog.parquet` and count rows.
   - Compute `baseSize = totalEntries - variantCatalogCount`; call Python adapter: `uv run python -m processes.field_sampler.adapter --slate-id <id> --seed <seed> --config-kv field_size=<baseSize> ... --input <variant_catalog>`.
   - Adapter generates base field then injects catalog rows; response: `{ ok, runId, field_path, metrics_path }`.
   - Pattern mirrors optimizer API spawn logic【F:app/api/optimize/route.ts†L27-L63】.

2. **GET `/api/runs?module=field`**
   - Existing endpoint already lists runs by module【F:app/api/runs/route.ts†L13-L51】; used to populate run picker.

3. **GET `/api/runs/{slate}/field/{run_id}`**
   - Extend dynamic run route to branch on `module === "field"` and serve `field.parquet` + `metrics.parquet`, transforming parquet rows to `LineupViews` shape (players, score, salary, source) before returning【F:app/api/runs/[slate]/[module]/[run_id]/route.ts†L14-L24】.

4. **Variant Injection Logic**
   - Field Sampler **does not** seed generation with the Variant Catalog. Instead:
     1. Generate `baseSize` public lineups using projections and contest rules.
     2. Inject Variant Catalog lineups into the field post-generation with provenance `source="injected"`【F:processes/field_sampler/injection_model.py†L45-L95】.
     3. Final entrants = `baseSize + variantCatalogCount` = `totalEntries`.

---

## 4. Error States

| Scenario | UX Response | Mitigation |
|----------|-------------|------------|
| Missing variant run selection | Disable run button, inline message “Select variant catalog for injection” |
| `total_entries < variant_catalog_count` | Show error toast and prevent run |
| Adapter process exit ≠ 0 | Surface toast with stderr, keep previous state |
| Invalid config keys | Adapter warns on unknown keys; display warning banner |
| Generated base field size 0 | Show info toast + empty grid |
| API timeouts / fetch errors | Display retry option and log to console |

---

## 5. Metrics & Lineup Grid

1. **Field Metrics**
   - Parse `metrics.parquet` conforming to `field_metrics` schema: coverage per player/team/position, `duplication_risk`, `pairwise_jaccard` histogram【F:pipeline/schemas/field_metrics.schema.yaml†L1-L40】.
   - Display aggregate cards for duplication risk and top coverage (sortable tables for player/team/position exposure).

2. **Lineup Grid Elements**
   - Table shows `lineup_id`, `score`, `salary_used`, `own_avg`, `num_uniques_in_pool`, `source`, DK slot columns etc., derived from `LineupViews` transformation and `LineupTable` columns【F:components/lineups/LineupViews.tsx†L20-L59】【F:lib/table/columns.tsx†L7-L31】.
   - Cards mode reuses existing `LineupGrid` for visual parity.

---

## 6. Integration with Unified Pipeline

- Field Sampler is step 3 in pipeline: builds base field, then injects Variant Catalog, before GPP simulation【F:docs/PRPs/PRP-PIPE-00-Pipeline-Overview-20250909-003232.md†L10-L18】.
- Adapter writes artifacts under `runs/<slate>/field/<run_id>/` with `field.parquet`, `metrics.parquet`, `manifest.json`, and appends to `registry/runs.parquet` (API surfaces these for UI).
- Page should store `run_id` and run metadata in `useRunStore`-like state for later pipeline stages.

---

## 7. Acceptance Criteria

- User configures contest settings, selects variant run, executes sampler, and views merged field in cards/table with source labels.
- API returns run metadata and lineup data consistent with `LineupTableData` schema plus `source`.
- Metrics panel shows duplication risk and coverage summaries parsed from `metrics.parquet`.
- Run artifacts registered and retrievable via `/api/runs` endpoints.
- Base field size + injected count equals user-specified `total_entries`.
- Error scenarios handled with clear feedback.

---

## 8. References
- Field injection model implementation【F:processes/field_sampler/injection_model.py†L45-L95】
- Field metrics schema【F:pipeline/schemas/field_metrics.schema.yaml†L1-L40】
- Lineup views and table columns【F:components/lineups/LineupViews.tsx†L1-L120】【F:lib/table/columns.tsx†L7-L31】
