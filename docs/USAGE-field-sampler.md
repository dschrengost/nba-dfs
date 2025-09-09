# Field Sampler Usage

This module builds a public field of DraftKings NBA lineups from projections
and then injects our variant catalog entries.

## Config

* `field_size` – number of public lineups to sample
* `seed` – RNG seed for determinism
* `site` – site identifier (`dk`)
* `slate_id` – slate identifier

## Running

```python
import pandas as pd
from processes.field_sampler import injection_model as fs

projections = pd.read_csv("projections.csv")
variant_catalog = pd.read_json("variant_catalog.jsonl", lines=True)
fs.build_field(
    projections,
    field_size=100,
    seed=42,
    slate_id="20250101_NBA",
    variant_catalog=variant_catalog,
)
```

## Outputs

Artifacts are written under `./artifacts/`:

* `field_base.jsonl` – sampled public field
* `field_merged.jsonl` – field with our injected lineups
* `metrics.json` – counts and run metadata
* `audit_fs.md` – summary report
