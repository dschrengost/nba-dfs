# PRP-INGEST-03 — CSV Ingestion, Validation, and Normalization

**Owner:** Agent A  
**Repo:** `nba-dfs`  
**Scope:** Wire the Upload Dropzone to parse `projections.csv` and `player_ids.csv`, validate with Zod, normalize to canonical models, and surface structured data to the app state (no optimizer yet).

---

## Deliverables
1) **Parsing & Validation**
- Zod schemas for both files; column alias mapping; numeric coercion.
- Streaming CSV parser (Papaparse) for large files.

2) **Normalization**
- Canonical `Player`, `Projection`, `MergedPlayer` types in `lib/domain/types.ts`.
- Join on `player_id`; expose merged list + lookup maps.

3) **State**
- Client store (`lib/state/ingest-store.ts`) with data, status, errors.
- Upload component calls `ingestCsv(files)`; expose ingest summary.

4) **Diagnostics**
- Ingest summary shown in Metrics drawer: rows parsed, merged, dropped, unknown columns.

5) **Fixtures & Tests**
- `fixtures/` sample CSVs + unit tests for schema, mapping, join, coercion.

---

## File Plan
```
lib/domain/types.ts
lib/ingest/schemas.ts
lib/ingest/parse.ts
lib/ingest/normalize.ts
lib/state/ingest-store.ts
components/ui/UploadDropzone.tsx
components/metrics/IngestSummary.tsx
fixtures/projections.csv
fixtures/player_ids.csv
```

## Acceptance Criteria
- Dropping the two CSVs populates the store with merged players (N > 0).
- Invalid/missing columns are reported; coercion handled.
- Large files don’t freeze the UI (streaming + yielding).
- Metrics drawer shows ingest summary.  
- Tests pass for schema and normalization logic.

**Start:** `git checkout -b feature/ingest-03` → PR → tag `v0.12.0`.
