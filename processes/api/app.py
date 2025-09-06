from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, cast

import pandas as pd
from fastapi import FastAPI, HTTPException

from processes.orchestrator import adapter as orch

app = FastAPI()

_RUNS: dict[str, dict[str, Any]] = {}
_METRICS: dict[str, str] = {}


@app.post("/run/orchestrator")  # type: ignore[misc]
def run_orchestrator(payload: dict[str, Any]) -> dict[str, Any]:
    slate_id = str(payload.get("slate_id"))
    config = payload.get("config")
    if not slate_id or not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="slate_id and config required")

    out_root = Path(str(payload.get("out_root", "data")))
    schemas_root = Path(str(payload.get("schemas_root", "pipeline/schemas")))
    validate = bool(payload.get("validate", True))
    dry_run = bool(payload.get("dry_run", False))
    verbose = bool(payload.get("verbose", False))

    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "config.json"
        cfg_path.write_text(json.dumps(config), encoding="utf-8")
        res = orch.run_bundle(
            slate_id=slate_id,
            config_path=cfg_path,
            config_kv=None,
            out_root=out_root,
            schemas_root=schemas_root,
            validate=validate,
            dry_run=dry_run,
            verbose=verbose,
        )

    bundle_id = str(res.get("bundle_id"))
    bundle_path = Path(res.get("bundle_path", ""))
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        stages = {s["name"]: s["run_id"] for s in bundle.get("stages", [])}
        res["stages"] = stages
        _RUNS[bundle_id] = {"bundle_path": str(bundle_path)}
        for s in bundle.get("stages", []):
            if s.get("name") == "sim" and s.get("primary_output"):
                sim_run_id = s["run_id"]
                metrics_path = Path(str(s["primary_output"])).with_name(
                    "metrics.parquet"
                )
                _METRICS[sim_run_id] = str(metrics_path)
    return cast(dict[str, Any], res)


@app.get("/runs/{run_id}")  # type: ignore[misc]
def get_run(run_id: str) -> dict[str, Any]:
    info = _RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="run not found")
    bundle_path = Path(info["bundle_path"])
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="bundle manifest not found")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], bundle)


@app.get("/metrics/{run_id}")  # type: ignore[misc]
def get_metrics(run_id: str) -> list[dict[str, Any]]:
    path_str = _METRICS.get(run_id)
    if not path_str:
        raise HTTPException(status_code=404, detail="metrics not found")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="metrics not found")
    df = pd.read_parquet(path)
    return cast(list[dict[str, Any]], df.to_dict(orient="records"))
