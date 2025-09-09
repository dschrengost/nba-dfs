
# PRP-ORCH-01 — One-Command End-to-End Orchestration
**Date:** 2025-09-09  
**Owner:** Daniel S. (solo)  
**Status:** Proposed

---

## GitHub Actions (Start)
- **Create feature branch:** `git switch -c feat/orch-01-one-command`
- **Open draft PR:** `gh pr create -B main -t "PRP-ORCH-01: one-command run orchestration" -b "Implements e2e orchestrated flow (variants → optimizer → field sampler → gpp_sim) with run registry + artifacts." -d`

---

## Summary
Stitch a **single, deterministic run pipeline** that executes:
**variants → optimizer → field_sampler → gpp_sim → metrics/export**, writing artifacts and metrics under a **single `run_id`** and updating the **runs registry**. Provide both **CLI** and **API** entry points, minimal configuration, and clean logs.

### Goals
- One command (CLI + API) to execute end-to-end.
- Consistent `run_id` + artifact layout under `runs/`.
- Read/write through existing **registry** + **pipeline.io**.
- Emit baseline **sim metrics** (ROI/finish percentiles/dupe bins) and **DK CSV export** for the selected lineup set.
- Deterministic seeding and full observability (logs + diagnostics blob).

### Non‑Goals
- Rewriting individual module logic (use current adapters).
- Full legacy removal (keep `_legacy/` intact but unused by default).
- Fancy UI polish (separate PRP-UI-01).

---

## Allowed Paths
```
processes/orchestrator/**
processes/api/**
pipeline/io/**
pipeline/registry/**
pipeline/schemas/**
app/api/runs/**
docs/PRPs/PRP-ORCH-01-*.md
tests/orchestrator/**
.github/workflows/**
```

---

## High‑Level Flow
1. Resolve slate + inputs via **registry**.
2. Generate **variant catalog** (processes/variants adapter).
3. Run **optimizer** with catalog → DK‑valid lineups.
4. **Field sampler**: sample field / produce entrants telemetry.
5. **GPP simulator**: simulate contest outcomes.
6. Compute **metrics**; write **artifacts**; update **runs registry**.

---

## Artifact Layout (Single `run_id`)
```
runs/{slate_id}/{run_id}/
  manifest.json                # module versions, seeds, paths, timings
  diagnostics.json             # per-module diagnostics
  variants/                    # catalog.* (parquet/csv), summary.json
  optimizer/
    lineups.parquet            # canonical output
    dk_export.csv              # DK uploadable
    metrics.json
  field_sampler/
    entrants.parquet
    telemetry.json
    metrics.json
  sim/
    results.parquet
    metrics.json               # ROI, finish pctiles, dup bins
  export/
    summary.md                 # compact human summary
```

> `run_id` format: `YYYYMMDD-HHMMSS-<shorthash>`; seed recorded under `manifest.json`.

---

## Data Contracts (schemas to reference)
- `pipeline/schemas/variant_catalog.schema.yaml`
- `pipeline/schemas/optimizer_output.schema.yaml`
- `pipeline/schemas/field_sampler_output.schema.yaml`
- `pipeline/schemas/sim_metrics.schema.yaml`
- `pipeline/schemas/run_manifest.schema.yaml` *(new, in this PR)*

---

## CLI
Add module: `processes/orchestrator/cli.py`

### Usage
```bash
uv run python -m processes.orchestrator run   --slate 2025-10-25   --contest "DK_MME_20"   --seed 1337   --variants-config configs/variants/default.yaml   --optimizer-config configs/optimizer/default.yaml   --sampler-config configs/field_sampler/default.yaml   --sim-config configs/sim/default.yaml   --tag "mvp-e2e"
```
- Returns `run_id`; prints artifact root + short summary table.

### Minimal Pseudocode
```python
def run(opts):
    ctx = resolve_context(opts)  # registry + paths + slate
    run_id = make_run_id(opts.seed)
    with run_context(run_id, ctx) as rc:
        vc, vdiag = variants.generate(ctx, opts.variants_config, seed=opts.seed)
        lps, odiag = optimizer.build(vc, opts.optimizer_config, seed=opts.seed)
        entrants, fdiag = field_sampler.sample(lps, opts.sampler_config, seed=opts.seed)
        simres, sdiag = gpp_sim.run(entrants, opts.sim_config, seed=opts.seed)

        metrics = compute_metrics(simres)  # ROI, pctiles, dup bins
        write_artifacts(run_id, vc, lps, entrants, simres, metrics, diagnostics=[vdiag, odiag, fdiag, sdiag])
        update_runs_registry(run_id, ctx, metrics, tag=opts.tag)
    return run_id
```

---

## API
Create route: `app/api/runs/route.ts` (Next.js) or **FastAPI** under `processes/api/orchestrator.py` (thin wrapper).  
**POST** `/api/runs` → body mirrors CLI flags → returns ``{ run_id, artifact_path, metrics_head }``.

---

## Logging & Determinism
- Set **global seed** (numpy/random) once; pass to each module.
- Include module seeds in `manifest.json` with versions (git `HEAD` short SHA) and timestamps.
- Use structured logs (JSON lines) under `runs/{slate_id}/{run_id}/{module}/logs.jsonl`.

---

## Tests (focused)
Location: `tests/orchestrator/`
- **test_run_smoke.py** — e2e smoke; asserts artifacts exist + schemas validate.
- **test_registry_resolution.py** — registry → resolved inputs for slate/contest.
- **test_determinism.py** — same seed → stable outputs hashes (sampling tolerance where applicable).
- **test_metrics_contract.py** — sim metrics match schema and invariants (e.g., ROI mean around field avg).

---

## CI Additions
- Ensure orchestration smoke test runs with `-k orchestrator` marker.
- Cache UV; run `ruff`, `black`, `mypy`, `pytest` in workflow.
- Artifact upload on PR (optional): store `summary.md` from test run.

---

## Acceptance Criteria
- [ ] **Single CLI** command runs full pipeline and returns `run_id`.
- [ ] Artifacts written exactly under the **Artifact Layout** above.
- [ ] `manifest.json` + `diagnostics.json` present and valid.
- [ ] **DK CSV** exported under `optimizer/dk_export.csv`.
- [ ] **Sim metrics** computed and saved under `sim/metrics.json` and meet schema.
- [ ] **Runs registry** updated with `(run_id, slate_id, contest, tag, paths, metrics_head)`.
- [ ] E2E tests pass locally and in CI (`pytest -k orchestrator -q`).

---

## Rollback Plan
- Feature is additive; guarded by new CLI/API only.
- Revert by removing `processes/orchestrator/**` and API route; no data migration required.

---

## Risks / Mitigations
- **Cross‑module contract drift** → lock via schema validation on each boundary.
- **Non‑determinism in sampling** → pass seed + document tolerance; snapshot hashes.
- **Long‑running tests** → keep orchestrator smoke minimal (tiny sample sizes).

---

## Developer Notes
- Prefer `pipeline/io` helpers for all R/W (no ad‑hoc `pd.read_*` in orchestrator).
- Keep orchestrator **thin**: call adapters; do not embed business logic.
- Return **compact** `metrics_head` for the UI ``{roi_mean, roi_p50, dup_p95}``.

---

## GitHub Actions (End)
- **Push branch:** `git push -u origin HEAD`
- **Mark PR ready:** `gh pr ready`
- **Rebase before merge:** `git fetch origin && git rebase origin/main`
- **Merge:** `gh pr merge --squash --delete-branch`
- **Post‑merge tag (optional):** `git tag -a orch-01 -m "One-command orchestration" && git push --tags`

---

## Appendix — Minimal DX Helpers (optional)
- `scripts/run_orch.sh` small wrapper calling the CLI with config presets.
- `app/api/runs/[run_id]/route.ts` GET for run summary (reads `summary.md`).
