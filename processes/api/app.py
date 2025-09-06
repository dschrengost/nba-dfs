from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd
from fastapi import FastAPI, HTTPException

from processes.api.models import (
    BundleManifest,
    OrchestratorRunRequest,
    OrchestratorRunResponse,
)
from processes.orchestrator import adapter as orch

app = FastAPI()

_RUNS: dict[str, dict[str, Any]] = {}
_METRICS: dict[str, str] = {}


@app.get("/health")  # type: ignore[misc]
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": "0.1.0",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/run/orchestrator", response_model=OrchestratorRunResponse)  # type: ignore[misc]
def run_orchestrator(req: OrchestratorRunRequest) -> OrchestratorRunResponse:
    out_root = Path(req.out_root)
    schemas_root = Path(req.schemas_root)

    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "config.json"
        cfg_path.write_text(
            json.dumps(req.config.model_dump(mode="json", exclude_none=True)),
            encoding="utf-8",
        )
        res = orch.run_bundle(
            slate_id=req.slate_id,
            config_path=cfg_path,
            config_kv=None,
            out_root=out_root,
            schemas_root=schemas_root,
            validate=req.validate,
            dry_run=req.dry_run,
            verbose=req.verbose,
        )

    bundle_id = str(res.get("bundle_id"))
    bundle_path = Path(str(res.get("bundle_path", "")))
    stages_map: dict[str, str] = {}
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        for s in bundle.get("stages", []):
            name = str(s.get("name"))
            run_id = str(s.get("run_id"))
            stages_map[name] = run_id
            if name == "sim" and s.get("primary_output"):
                metrics_path = Path(str(s["primary_output"])).with_name(
                    "metrics.parquet"
                )
                _METRICS[run_id] = str(metrics_path)
        _RUNS[bundle_id] = {"bundle_path": str(bundle_path)}

    return OrchestratorRunResponse(
        bundle_id=bundle_id,
        bundle_path=str(bundle_path),
        stages=stages_map,
        run_registry_path=None,
    )


@app.get("/runs/{run_id}", response_model=BundleManifest)  # type: ignore[misc]
def get_run(run_id: str) -> BundleManifest:
    info = _RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="run not found")
    bundle_path = Path(info["bundle_path"])
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="bundle manifest not found")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    return cast(BundleManifest, BundleManifest.model_validate(bundle))


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
