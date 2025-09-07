Implements PRP-INGEST-03 T0→T5

Changes:
- T0: Add domain types and Zod CSV schemas (players, projections) with alias maps.
- T1: Streaming parser using PapaParse + Zod validation, unknown column reporting.
- T2: Normalization + inner join on player_id_dk to canonical types.
- T3: Zustand ingest-store with status, summary, merged data, and errors.
- T4: Wire UploadDropzone to ingestCsv(); support multi-file uploads.
- T5: Add IngestSummary to Metrics drawer.
- Tests: Add vitest + unit specs; Fixtures under fixtures/.

Notes:
- New deps: zod, papaparse, zustand, vitest (dev). Lockfile updated.
- No writes occur under data/ or runs/.
- Determinism: parsing/normalization are pure; no global state.
- Schema contracts follow AGENTS.md house schema; IDs persist through merged data.

Validation:
- npm test passes (3 specs).
- UI integration compiles locally (Next).

Follow-ups:
- Add more robust CSV kind detection beyond filename.
- Expand metrics collection (null rates, dupe rates) as per PRP-8.
