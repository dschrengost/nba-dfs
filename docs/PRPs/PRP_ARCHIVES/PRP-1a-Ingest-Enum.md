
# PRP-1a: Extend RunTypeEnum with `ingest` + Align Manifests/Tests

## Objective
Add a first-class `ingest` run type to the schema pack and update the ingestion CLI, manifests, and tests to use it (instead of temporarily using `variants`).

## Start Bookend — Branch
```
PRP Start → branch=feature/ingest-enum
```

## Scope & Tasks
1. **Schema update**
   - `pipeline/schemas/common.types.yaml`: extend `RunTypeEnum` with `ingest`.
   - `pipeline/schemas/manifest.schema.yaml`: no structural change, but ensure `run_type` example includes `ingest`.
   - `pipeline/schemas/runs_registry.schema.yaml`: examples may include `ingest`.

2. **Versioning**
   - Bump **MINOR** version for each changed schema (SemVer policy).
   - Update `pipeline/schemas/README.md` change log with one-line entry.

3. **Code alignment**
   - Update ingestion CLI to emit `run_type="ingest"` in manifest and registry rows.

4. **Tests**
   - Adjust tests asserting run type to expect `ingest`.
   - Add a small assertion in `test_manifest_registry_write.py` for `run_type == "ingest"`.

## Acceptance Criteria
- Schemas validate (JSON Schema 2020-12) after enum change.
- New manifests created by the CLI show `"run_type": "ingest"`.
- Tests pass locally and in CI.
- README change log updated.

## End Bookend — Merge & Tag
```
PRP End → branch=feature/ingest-enum
```
