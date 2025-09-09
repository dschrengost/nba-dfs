
# PRP-FS-03 — Optional Stopgap CLI Wrapper (Adapter-First)

**Owner:** Cloud Agent  
**Repo:** `nba-dfs`  
**Branch:** `feat/fs-03-cli-wrapper` (optional)

---

## Goal
Provide a temporary CLI that runs via the existing adapter/external impl (`FIELD_SAMPLER_IMPL`) while the core engine lands.

## Deliverables
- `tools/sample_field_cli.py` — wrapper that reads canonical inputs, resolves impl, emits `field_base.jsonl`/`metrics.json`.
- Ensures outputs match `field.schema.yaml` and `field_metrics.schema.yaml`.
- Docs: `docs/USAGE-field-sampler-cli.md`.

## Acceptance
- End-to-end run with adapter on a sample slate.
- Outputs include required metadata and pass schema checks.
- Determinism of metadata with fixed seed.

## GitHub Actions
**Start:** create `feat/fs-03-cli-wrapper`, push, Draft PR  
**End:** CI green; docs added; rebase; squash-merge; tag `v0.4.1-fs-cli`
