# Field Sampler Usage

The field sampler builds a public field of DraftKings NBA lineups from a
projections file. The core engine lives in `field_sampler.engine` and may be
invoked either from Python or the CLI.

## Config

Required knobs:

* `field_size` – number of public lineups to sample
* `seed` – RNG seed for determinism
* `site` – site identifier (`dk`)
* `slate_id` – slate identifier
* `salary_cap` – contest salary cap (default 50000)
* `max_per_team` – max players per team (default 4)

## Running from Python

```python
import pandas as pd
from field_sampler.engine import SamplerEngine

projections = pd.read_csv("projections.csv")
engine = SamplerEngine(projections, seed=42, slate_id="20250101_NBA")
engine.generate(100)
```

## CLI

```bash
python -m tools.sample_field \
  --projections projections.csv \
  --contest-config contest_config.json \
  --field-size 100 \
  --seed 42 \
  --slate-id 20250101_NBA
```

## Inputs

* `projections.csv` – player projections with columns
  `player_id,team,positions,salary,ownership`
* `contest_config.json` – provides `salary_cap` and `max_per_team`
* `slate.csv` – optional slate metadata (unused)

## Outputs

Artifacts are written under `./artifacts/`:

* `field_base.jsonl` – sampled public field
* `metrics.json` – run metadata
* `audit_fs.md` – summary report
