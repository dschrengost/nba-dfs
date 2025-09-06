from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd
from fastapi import FastAPI, HTTPException, Response

from processes.api.models import (
    BundleManifest,
    OrchestratorRunRequest,
    OrchestratorRunResponse,
    RunRegistryRow,
    RunsListResponse,
)
from processes.dk_export import writer as dk_writer
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


@app.get("/runs", response_model=RunsListResponse)  # type: ignore[misc]
def list_runs(registry_path: str | None = None) -> RunsListResponse:
    """List runs discovered in the registry parquet.

    If the registry does not exist, returns an empty list.
    """
    reg_path = Path(registry_path or Path("data") / "registry" / "runs.parquet")
    if not reg_path.exists():
        return RunsListResponse(runs=[])
    try:
        df = pd.read_parquet(reg_path)
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"failed to read registry: {e}",
        ) from e
    rows = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    models = [RunRegistryRow.model_validate(r) for r in rows]
    return RunsListResponse(runs=models)


def _find_manifest_for_run(run_id: str, runs_root: Path) -> tuple[str, Path]:
    """Return (run_type, manifest_path) for the first matching run dir.

    Searches known run types under `runs_root`.
    """
    for rt in ("sim", "variants", "field", "optimizer", "ingest", "metrics"):
        m = runs_root / rt / run_id / "manifest.json"
        if m.exists():
            return rt, m
    raise FileNotFoundError("manifest not found for run_id")


@app.get("/export/dk/{run_id}")  # type: ignore[misc]
def export_dk_csv(
    run_id: str,
    runs_root: str | None = None,
    top_n: int = 20,
    dedupe: bool = True,
) -> Response:
    """Generate a DK-uploadable CSV from a run (sim or variants).

    - For sim runs: ranks entrants by EV (mean prize) from sim_results.
    - For variants runs: uses variant_catalog order (first N) as a simple heuristic.
    """
    root = Path(runs_root or "runs")
    try:
        run_type, manifest_path = _find_manifest_for_run(run_id, root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="run manifest not found") from e

    if run_type == "sim":
        sim_path, field_path = dk_writer.discover_from_sim_run(run_id, root)
        sim_df = pd.read_parquet(sim_path)
        field_df = pd.read_parquet(field_path)
        export_df = dk_writer.build_export_df(
            sim_df, field_df, top_n=int(top_n), dedupe=bool(dedupe)
        )
    elif run_type == "variants":
        # Discover variant_catalog and derive export rows from export_csv_row
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        catalog_path: Path | None = None
        for obj in data.get("outputs", []):
            if obj.get("kind") == "variant_catalog":
                catalog_path = Path(str(obj["path"]))
                break
        if catalog_path is None or not catalog_path.exists():
            raise HTTPException(status_code=404, detail="variant catalog not found")
        cat_df = pd.read_parquet(catalog_path)
        # Build DataFrame with DK columns from export_csv_row
        rows: list[dict[str, Any]] = []
        for _, row in cat_df.head(int(top_n)).iterrows():
            tokens = dk_writer._parse_export_row(
                str(row.get("export_csv_row", ""))
            )
            players = [tokens.get(slot, "") for slot in dk_writer.DK_SLOTS_ORDER]
            if "" in players:
                raise HTTPException(
                    status_code=400,
                    detail="invalid export_csv_row in catalog",
                )
            rows.append(dict(zip(dk_writer.DK_SLOTS_ORDER, players, strict=True)))
        export_df = pd.DataFrame(rows)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported run_type: {run_type}")

    # Serialize CSV with DK header order only
    csv_text = export_df.to_csv(columns=dk_writer.DK_SLOTS_ORDER, index=False)
    return Response(content=csv_text, media_type="text/csv")


@app.get("/logs/{run_id}")  # type: ignore[misc]
def get_logs(run_id: str, runs_root: str | None = None) -> dict[str, Any]:
    """Return placeholder logs/debug info for a run.

    If a `logs.txt` exists under the run dir, return its content; otherwise a stub.
    """
    root = Path(runs_root or "runs")
    try:
        run_type, manifest_path = _find_manifest_for_run(run_id, root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="run manifest not found") from e
    run_dir = manifest_path.parent
    logs_path = run_dir / "logs.txt"
    if logs_path.exists():
        content = logs_path.read_text(encoding="utf-8")
        return {"run_id": run_id, "run_type": run_type, "logs": content}
    # fallback placeholder
    return {"run_id": run_id, "run_type": run_type, "message": "logs not available"}
