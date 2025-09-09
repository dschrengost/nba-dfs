
# PRP-1b: Runtime JSON Schema Validation for Manifests & Registry

## Objective
Add runtime validation to the ingestion CLI so that `manifest.json` and append operations to `runs.parquet` conform to their JSON Schemas before writing—failing fast on violations.

## Start Bookend — Branch
```
PRP Start → branch=feature/ingest-runtime-validation
```

## Scope & Tasks
1. **Validator utility**
   - Lightweight helper that loads JSON Schemas from `pipeline/schemas/` and validates python dicts using `jsonschema` (Draft 2020-12).

2. **Integration points**
   - Validate `manifest` object **before** writing JSON.
   - Validate a constructed `runs_registry` row **before** append.
   - On failure: log concise error, exit non-zero, do not write partial artifacts.

3. **CLI flags**
   - `--validate/--no-validate` (default: `--validate`).
   - `--schemas-root` override (default: `pipeline/schemas`).

4. **Tests**
   - Positive: current flow validates successfully.
   - Negative: inject an invalid field (e.g., wrong `run_type` or missing `content_sha256`) and assert non-zero exit and no files written.

5. **Docs**
   - Add a short section to `pipeline/ingest/README.md` on validation behavior and flags.

## Acceptance Criteria
- Validation failures block writes and return non-zero exit codes.
- Positive path untouched performance-wise (validate once per run).
- CI green with added tests.

## End Bookend — Merge & Tag
```
PRP End → branch=feature/ingest-runtime-validation
```
