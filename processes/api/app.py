from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from processes.api.models import (
    BundleManifest,
    ErrorResponse,
    MetricsHead,
    OrchestratedRunRequest,
    OrchestratedRunResponse,
    OrchestratorRunRequest,
    OrchestratorRunResponse,
    RunRegistryRow,
    RunsListResponse,
)
from processes.dk_export import writer as dk_writer
from processes.orchestrator import adapter as orch
from processes.orchestrator.core import run_orchestrated_pipeline

app = FastAPI()

logger = logging.getLogger("processes.api")

_RUNS: dict[str, dict[str, Any]] = {}
_METRICS: dict[str, str] = {}


@app.get("/health")  # type: ignore[misc]
def health() -> dict[str, Any]:
    t0 = time.time()
    logger.info(json.dumps({"event": "api_enter", "endpoint": "/health"}))
    out = {
        "ok": True,
        "version": "0.1.0",
        "time": datetime.now(UTC).isoformat(),
    }
    dt = time.time() - t0
    logger.info(json.dumps({"event": "api_exit", "endpoint": "/health", "dt_s": round(dt, 6)}))
    return out


@app.post(
    "/run/orchestrator",
    response_model=OrchestratorRunResponse | ErrorResponse,
)  # type: ignore[misc]
def run_orchestrator(
    req: OrchestratorRunRequest, response: Response
) -> OrchestratorRunResponse | ErrorResponse:
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/run/orchestrator",
                "slate_id": req.slate_id,
            }
        )
    )
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
                metrics_path = Path(str(s["primary_output"])).with_name("metrics.parquet")
                _METRICS[run_id] = str(metrics_path)
        _RUNS[bundle_id] = {"bundle_path": str(bundle_path)}

    out = OrchestratorRunResponse(
        bundle_id=bundle_id,
        bundle_path=str(bundle_path),
        stages=stages_map,
        run_registry_path=None,
    )
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/run/orchestrator",
                "dt_s": round(dt, 6),
                "bundle_id": bundle_id,
            }
        )
    )
    return out


@app.get(
    "/runs/{run_id}",
    response_model=BundleManifest | ErrorResponse,
)  # type: ignore[misc]
def get_run(run_id: str, response: Response) -> BundleManifest | ErrorResponse:
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/runs/{run_id}",
                "run_id": run_id,
            }
        )
    )
    info = _RUNS.get(run_id)
    if not info:
        response.status_code = 404
        return ErrorResponse(error="not_found", detail="run not found")
    bundle_path = Path(info["bundle_path"])
    if not bundle_path.exists():
        response.status_code = 404
        return ErrorResponse(error="not_found", detail="bundle manifest not found")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    out = cast(BundleManifest, BundleManifest.model_validate(bundle))
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/runs/{run_id}",
                "dt_s": round(dt, 6),
            }
        )
    )
    return out


@app.get(
    "/metrics/{run_id}",
    response_model=list[dict[str, Any]] | ErrorResponse,
)  # type: ignore[misc]
def get_metrics(run_id: str, response: Response) -> list[dict[str, Any]] | ErrorResponse:
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/metrics/{run_id}",
                "run_id": run_id,
            }
        )
    )
    path_str = _METRICS.get(run_id)
    if not path_str:
        response.status_code = 404
        return ErrorResponse(error="not_found", detail="metrics not found")
    path = Path(path_str)
    if not path.exists():
        response.status_code = 404
        return ErrorResponse(error="not_found", detail="metrics not found")
    df = pd.read_parquet(path)
    out = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/metrics/{run_id}",
                "dt_s": round(dt, 6),
            }
        )
    )
    return out


@app.get(
    "/runs",
    response_model=RunsListResponse | ErrorResponse,
)  # type: ignore[misc]
def list_runs(
    response: Response, registry_path: str | None = None
) -> RunsListResponse | ErrorResponse:
    """List runs discovered in the registry parquet.

    Returns 404 if the registry is missing.
    """
    t0 = time.time()
    # Response provided by FastAPI injection
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/runs",
                "registry_path": registry_path,
            }
        )
    )
    reg_path = Path(registry_path or Path("data") / "registry" / "runs.parquet")
    if not reg_path.exists():
        response.status_code = 404
        return ErrorResponse(error="not_found", detail="registry not found")
    try:
        df = pd.read_parquet(reg_path)
    except Exception as e:  # pragma: no cover
        response.status_code = 500
        return ErrorResponse(error="internal_error", detail=f"failed to read registry: {e}")
    rows = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    models = [RunRegistryRow.model_validate(r) for r in rows]
    out = RunsListResponse(runs=models)
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/runs",
                "dt_s": round(dt, 6),
                "count": len(models),
            }
        )
    )
    return out


def _find_manifest_for_run(run_id: str, runs_root: Path) -> tuple[str, Path]:
    """Return (run_type, manifest_path) for the first matching run dir.

    Searches known run types under `runs_root`.
    """
    for rt in ("sim", "variants", "field", "optimizer", "ingest", "metrics"):
        m = runs_root / rt / run_id / "manifest.json"
        if m.exists():
            return rt, m
    raise FileNotFoundError("manifest not found for run_id")


@app.get(
    "/export/dk/{run_id}",
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)  # type: ignore[misc]
def export_dk_csv(
    run_id: str,
    response: Response,
    runs_root: str | None = None,
    top_n: int = 20,
    dedupe: bool = True,
) -> Response:
    """Generate a DK-uploadable CSV from a run (sim or variants).

    - For sim runs: ranks entrants by EV (mean prize) from sim_results.
    - For variants runs: uses variant_catalog order (first N) and `export_csv_row`.

    On error, returns JSON matching ErrorResponse model.
    """
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/export/dk/{run_id}",
                "run_id": run_id,
                "top_n": top_n,
                "dedupe": bool(dedupe),
            }
        )
    )
    # Response provided by FastAPI injection
    root = Path(runs_root or "runs")
    try:
        run_type, manifest_path = _find_manifest_for_run(run_id, root)
    except FileNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "detail": "run manifest not found"},
        )

    if run_type == "sim":
        try:
            sim_path, field_path = dk_writer.discover_from_sim_run(run_id, root)
            sim_df = pd.read_parquet(sim_path)
            field_df = pd.read_parquet(field_path)
            export_df = dk_writer.build_export_df(
                sim_df, field_df, top_n=int(top_n), dedupe=bool(dedupe)
            )
        except Exception as e:
            return JSONResponse(
                status_code=422,
                content={"error": "invalid_export", "detail": str(e)},
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
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "detail": "variant catalog not found",
                },
            )
        cat_df = pd.read_parquet(catalog_path)
        if "export_csv_row" not in cat_df.columns:
            return JSONResponse(
                status_code=422,
                content={"error": "invalid_export", "detail": "export_csv_row missing"},
            )
        # Build DataFrame with DK columns from export_csv_row
        rows: list[dict[str, Any]] = []
        for _, row in cat_df.head(int(top_n)).iterrows():
            tokens = dk_writer._parse_export_row(str(row.get("export_csv_row", "")))
            players = [tokens.get(slot, "") for slot in dk_writer.DK_SLOTS_ORDER]
            if "" in players:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": "invalid_export",
                        "detail": "invalid export_csv_row in catalog",
                    },
                )
            rows.append(dict(zip(dk_writer.DK_SLOTS_ORDER, players, strict=True)))
        export_df = pd.DataFrame(rows)
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported_run_type", "detail": f"{run_type}"},
        )

    # Serialize CSV with DK header order only
    csv_text = export_df.to_csv(columns=dk_writer.DK_SLOTS_ORDER, index=False)
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/export/dk/{run_id}",
                "dt_s": round(dt, 6),
                "rows": int(len(export_df)),
            }
        )
    )
    return Response(content=csv_text, media_type="text/csv")


@app.get("/logs/{run_id}", response_model=dict[str, Any])  # type: ignore[misc]
def get_logs(run_id: str, runs_root: str | None = None) -> dict[str, Any]:
    """Return placeholder logs/debug info for a run.

    If a `logs.txt` exists under the run dir, return its content; otherwise a stub.
    """
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/logs/{run_id}",
                "run_id": run_id,
            }
        )
    )
    root = Path(runs_root or "runs")
    try:
        run_type, manifest_path = _find_manifest_for_run(run_id, root)
    except FileNotFoundError:
        return {"error": "not_found", "detail": "run manifest not found"}
    run_dir = manifest_path.parent
    logs_path = run_dir / "logs.txt"
    if logs_path.exists():
        content = logs_path.read_text(encoding="utf-8")
        out = {"run_id": run_id, "run_type": run_type, "logs": content}
    else:
        out = {"run_id": run_id, "run_type": run_type, "message": "logs not available"}
    dt = time.time() - t0
    logger.info(
        json.dumps(
            {
                "event": "api_exit",
                "endpoint": "/logs/{run_id}",
                "dt_s": round(dt, 6),
            }
        )
    )
    return out


# PRP-ORCH-01: One-Command End-to-End Orchestration API


@app.post(
    "/api/runs",
    response_model=OrchestratedRunResponse | ErrorResponse,
)  # type: ignore[misc]
def orchestrated_run(
    request: OrchestratedRunRequest,
    response: Response,
) -> OrchestratedRunResponse | ErrorResponse:
    """Execute the complete orchestrated pipeline via API.

    This mirrors the CLI interface but provides a web API for the orchestrated pipeline.
    Body mirrors CLI flags and returns run_id, artifact_path, and metrics_head.
    """
    t0 = time.time()
    logger.info(
        json.dumps(
            {
                "event": "api_enter",
                "endpoint": "/api/runs",
                "slate": request.slate,
                "contest": request.contest,
                "seed": request.seed,
            }
        )
    )

    try:
        # Convert string paths to Path objects
        variants_config = Path(request.variants_config)
        optimizer_config = Path(request.optimizer_config)
        sampler_config = Path(request.sampler_config)
        sim_config = Path(request.sim_config)
        out_root = Path(request.out_root)
        schemas_root = Path(request.schemas_root) if request.schemas_root else None

        # Execute the orchestrated pipeline
        result = run_orchestrated_pipeline(
            slate_id=request.slate,
            contest=request.contest,
            seed=request.seed,
            variants_config=variants_config,
            optimizer_config=optimizer_config,
            sampler_config=sampler_config,
            sim_config=sim_config,
            tag=request.tag,
            out_root=out_root,
            schemas_root=schemas_root,
            dry_run=request.dry_run,
            verbose=request.verbose,
        )

        if request.dry_run:
            # For dry runs, return a placeholder response
            dt = time.time() - t0
            logger.info(
                json.dumps(
                    {
                        "event": "api_exit",
                        "endpoint": "/api/runs",
                        "dt_s": round(dt, 6),
                        "dry_run": True,
                    }
                )
            )
            return OrchestratedRunResponse(
                run_id=result["run_id"],
                artifact_path="dry_run",
                metrics_head=MetricsHead(),
            )

        # Build response from successful run
        metrics_head_data = result.get("metrics_head", {})
        metrics_head = MetricsHead(
            roi_mean=metrics_head_data.get("roi_mean"),
            roi_p50=metrics_head_data.get("roi_p50"),
            dup_p95=metrics_head_data.get("dup_p95"),
        )

        api_response = OrchestratedRunResponse(
            run_id=result["run_id"],
            artifact_path=result["artifact_root"],
            metrics_head=metrics_head,
        )

        dt = time.time() - t0
        logger.info(
            json.dumps(
                {
                    "event": "api_exit",
                    "endpoint": "/api/runs",
                    "dt_s": round(dt, 6),
                    "run_id": result["run_id"],
                }
            )
        )

        return api_response

    except Exception as e:
        response.status_code = 500
        dt = time.time() - t0
        logger.error(
            json.dumps(
                {
                    "event": "api_error",
                    "endpoint": "/api/runs",
                    "dt_s": round(dt, 6),
                    "error": str(e),
                }
            )
        )
        return ErrorResponse(error="internal_error", detail=str(e))
