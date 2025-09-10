import pandas as pd
from pathlib import Path
from pipeline.io.validate import load_schema, validate_obj
from processes.orchestrator.core import _compute_sim_metrics


def _minimal_modules():
    return {
        k: {"version": "x", "run_id": "r", "manifest_path": "m"}
        for k in ["variants", "optimizer", "field_sampler", "gpp_sim"]
    }


def test_head_propagation():
    df = pd.DataFrame([
        {"prize": 10.0, "finish": 1, "dup_count": 1},
        {"prize": 0.0, "finish": 2, "dup_count": 1},
    ])
    metrics = _compute_sim_metrics(df)
    metrics_head = {
        "roi_mean": metrics["roi_mean"],
        "roi_p50": metrics["roi_p50"],
        "dup_p95": metrics["dup_p95"],
    }
    manifest = {
        "schema_version": "0.1.0",
        "run_id": "r1",
        "slate_id": "s1",
        "created_ts": "2025-01-01T00:00:00Z",
        "modules": _minimal_modules(),
        "seeds": {"global": 1},
        "artifact_paths": {
            "optimizer_lineups": "a",
            "optimizer_dk_export": "b",
            "sim_metrics": "c",
            "summary": "d",
        },
        "metrics_head": metrics_head,
    }
    schema = load_schema(Path("pipeline/schemas/run_manifest.schema.yaml"))
    validate_obj(schema, manifest, schemas_root=Path("pipeline/schemas"))
    assert manifest["metrics_head"] == metrics_head
