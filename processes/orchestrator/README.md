# Orchestrator (PRP-6)

Coordinates an end-to-end run: ingest → optimizer → variants → field → sim.

## CLI

```
python -m processes.orchestrator \
  --slate-id 20250101_NBA \
  --config /path/to/orchestrator.yaml \
  --out-root /tmp/dfs-run \
  --schemas-root pipeline/schemas \
  --validate \
  --verbose
```

Flags:
- `--config`: Single YAML/JSON file with per-stage blocks under keys
  `ingest`, `optimizer`, `variants`, `field`, `sim`.
- `--config-kv`: Optional inline overrides `key=value` (applied at the top level).
- `--dry-run`: Print the planned stages with resolved inputs, no execution.
- `--schemas-root`: Schema folder (defaults to repo `pipeline/schemas`).
- `--validate`: Toggle JSON-schema validation (passed down to stages).
- `--verbose`: Print a brief per-stage summary.

## Config Structure (example)

```yaml
slate_id: "20250101_NBA"
seeds:
  optimizer: 1
  variants: 2
  field: 3
  sim: 4

ingest:
  source: manual
  projections: /path/to/projections.csv
  player_ids: /path/to/player_ids.csv
  mapping: pipeline/ingest/mappings/example_source.yaml

optimizer:
  site: DK
  engine: cbc
  config: { num_lineups: 5 }

variants:
  config: { num_variants: 10 }

field:
  config: { field_size: 50 }

sim:
  config: { num_trials: 100 }
  # Either provide an explicit contest object or a path to a file
  contest:
    field_size: 50
    payout_curve:
      - { rank_start: 1, rank_end: 1, prize: 500 }
      - { rank_start: 2, rank_end: 2, prize: 200 }
      - { rank_start: 3, rank_end: 3, prize: 100 }
    entry_fee: 20
    rake: 0.15
    site: DK
```

## Artifacts

- `runs/orchestrator/<bundle_id>/bundle.json`: summary linking child run_ids and outputs.
- Stages write their own manifests and registry entries.

Note: Run Registry schema today does not include parent/child linkage; this
orchestrator does not mutate schema. Child runs are discoverable via their own
manifests and the bundle manifest.

