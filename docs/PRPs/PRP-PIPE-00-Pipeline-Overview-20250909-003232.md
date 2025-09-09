
# PRP-PIPE-00 — NBA-DFS Pipeline Overview (Injection Model)

**Owner:** Cloud Agent  
**Repo:** `nba-dfs` (monorepo)  
**Branches created by tasks below:** per-PRP

---

## Goal
Codify the revised pipeline: **Field Sampler builds a realistic field**, then **we inject our Variant Catalog** (our entries) for simulation/analysis. This keeps the field representative of public play instead of mirroring our own variants.

## High-Level Flow
1) **Data Intake** → normalized `projections.csv`, `player_ids.csv`, `slate.csv`, `contest_config.json`  
2) **Variant Builder (VB)** → produces `variant_catalog.jsonl|parquet` (our candidate entries)  
3) **Field Sampler (FS)** → generates **base field** using projections/ownership rules (**not** seeded by VB)  
4) **Injection Step** → merge our `variant_catalog` into the base field with provenance  
5) **GPP Simulator** → consumes merged field + contest structure → metrics/report
6) **Dash + Artifacts** → grids, exposures, ROI, dupes, leverage

## Core Invariants
- **Single validator source** used by VB, FS, Simulator IO checks.  
- **DK IDs** persist; no remap within a slate.  
- Artifacts carry `run_id`, `created_at`, `site`, `slate_id`, `source_branch`, `ruleset_version`.

## PRPs in this chain
- `PRP-FS-01` — Field Sampler (Injection Model, top-level spec)  
- `PRP-FS-02` — Validators + Core Sampler Engine  
- `PRP-FS-03` — CLI Wrapper (stopgap; optional)  
- `PRP-VB-01` — Variant Builder contract (minimal; to align with FS & sim)

## GitHub Actions (per PRP)
**Start:** create feature branch, commit PRP, push, open Draft PR  
**End:** CI green; audit updated (0 criticals); rebase main; squash-merge; tag
