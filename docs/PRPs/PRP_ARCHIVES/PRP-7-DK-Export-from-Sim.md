# PRP-7: DK CSV Export from Simulator + Entries Writer

## Goal
Produce a DraftKings Classic NBA–compliant CSV **from simulator outputs** (sim_results + field) and optionally **write into a user-provided DK entries CSV** (seeded by selected simulated entrants).

---

## Scope

### New module: `processes/dk_export/`
- `writer.py`: pure functions to shape DK rows from **sim results** joined to **field entrants**.
- `__main__.py`: CLI entry.

**Inputs (discovery + flags):**
- One of:
  - `--from-sim-run <run_id>` → resolves to `runs/sim/<run_id>/artifacts/{sim_results.parquet, metrics.parquet}` and `field.parquet` via manifest inputs.
  - `--sim-results <path>` and `--field <path>` (explicit paths).
- Optional selectors:
  - `--top-n <int>` (default 20).
  - `--min-ev <float>`.
  - `--include <id1,id2,...>` / `--exclude <id1,id2,...>`.
  - `--dedupe` (default on).

**Outputs:**
- `--out-csv <path>`: DK-uploadable CSV (header order fixed).
- `--entries-csv <path>` (optional): update a DK entries CSV in place or to `--entries-out <path>`.

**Behavior:**
- Read sim_results → pick entrants by selector.
- Join to field.parquet → build DK string (`PG,SG,SF,PF,C,G,F,UTIL`).
- Validate 8 slots, salary cap ≤ 50000, no blanks.
- Deduplicate by export row if needed.
- If entries-csv given, map selected entrants into rows and preserve others.

**Manifest (optional):**
- Write manifest under `runs/export/<export_id>/manifest.json` with:
  - `source_run_id`, `selected_entrant_ids`, `out_csv_path`, `entries_csv_in/out`, `created_ts`.
- Deterministic `export_id` from hashes of inputs + seed.

---

## CLI Examples

```
python -m processes.dk_export   --from-sim-run 20251101_180000_deadbee   --top-n 20   --out-csv data/exports/tournament_lineups.csv   --dedupe --verbose
```

```
python -m processes.dk_export   --from-sim-run 20251101_180000_deadbee   --top-n 20   --out-csv data/exports/tournament_lineups.csv   --entries-csv ~/Downloads/DK_entries.csv   --entries-out data/exports/DK_entries_filled.csv
```

---

## Tests

- `tests/test_dk_export_header_order.py`: header/order matches DK spec.
- `tests/test_dk_export_from_sim_topn.py`: top-N selection yields N rows.
- `tests/test_dk_export_dedupe.py`: duplicates handled with dedupe.
- `tests/test_dk_entries_writer_roundtrip.py`: round-trip update of entries template.
- `tests/test_dk_export_discovery_from_run.py`: discovery from sim run manifest.

Fixtures:
- `tests/fixtures/dk_entries_template.csv`.
- Reuse sim + field stubs.

---

## Branch & PR
- Branch: `feature/dk-export-from-sim`
- Scope: `processes/dk_export/**`, `tests/test_dk_export_*`, fixtures.
- PR Title: PRP-7: DK CSV export from simulator + entries writer.
