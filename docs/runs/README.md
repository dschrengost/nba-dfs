# Run Registry

Run outputs are persisted under the `runs/` directory using the structure:

```
runs/<SLATE_KEY>/<module>/<RUN_ID>/
  run_meta.json
  inputs_hash.json      # optional
  validation_metrics.json  # optional
  artifacts/
```

`run_meta.json` stores core metadata such as the module name, slate key, run id and
creation timestamp. Optional `inputs_hash.json` and `validation_metrics.json`
capture hashes of input files and validation statistics respectively.

Helpers in `src/runs/api.py` provide functions to save runs, list available runs
and prune old entries.
