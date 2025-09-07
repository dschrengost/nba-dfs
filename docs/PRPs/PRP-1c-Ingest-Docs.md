
# PRP-1c: Ingest Docs & CLI Flags

## Objective
Document the ingestion front door so users (and future agents) can operate it without reading code.

## Start Bookend — Branch
```
PRP Start → branch=feature/ingest-docs
```

## Scope
- Author `pipeline/ingest/README.md`:
  - Overview of ingestion flow
  - CLI usage and flags
  - Mapping catalog format (`pipeline/ingest/mappings/*.yaml`) with examples
  - Priority logic (“latest wins” + source precedence)
  - Lineage and `content_sha256`
  - Output paths and file naming
  - Validation behavior (`--validate/--no-validate`, `--schemas-root`)
  - Troubleshooting (common errors, schema failures)

- Author `pipeline/registry/README.md`:
  - Purpose of Run Registry
  - `runs.parquet` columns and how manifests reference outputs
  - How `run_id` is minted
  - How to query the latest run by `slate_id`

## Acceptance Criteria
- Docs render cleanly and match actual CLI flags and behaviors.
- Include copy‑paste CLI examples using `tests/fixtures/*.csv`.
- CI: markdownlint (if enabled) passes; otherwise include in standard lint workflow.

## End Bookend — Merge & Tag
```
PRP End → branch=feature/ingest-docs
```
