# PRP-6: Orchestrator and E2E Smoke

## Scope
- Add `processes/orchestrator/adapter.py` + CLI (`__main__.py`).
- Chain ingest → optimizer → variants → field_sampler → gpp_sim using the runs registry.
- Accept a single config file with per-stage blocks + `--config-kv` overrides.
- Generate a top-level `bundle.json` manifest linking child run_ids + outputs.
- Respect `--dry-run`, `--schemas-root`, `--validate`, `--verbose`.
- Deterministic seeds, threaded through each stage.
- E2E smoke test (stubs for optimizer, variants, field, sim).

## Artifacts
- `runs/orchestrator/<bundle_id>/bundle.json`
- Updated `registry/runs.parquet` with parent/child linkage.

## Tests
- `tests/test_orchestrator_smoke.py` — stubs only, ensures bundle.json created, all manifests valid.
- `tests/test_orchestrator_dry_run.py` — prints plan but does not execute.

## Docs
- `processes/orchestrator/README.md` — CLI usage, config structure, discovery rules.

## GitHub Actions
- **Start**: create branch `feature/orchestrator-e2e`
- **End**: open PR into `main` with summary of orchestrator, bundle manifest, and e2e smoke tests.
