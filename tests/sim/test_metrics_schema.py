import pandas as pd
from pathlib import Path
from pipeline.io.validate import load_schema, validate_obj
from processes.orchestrator.core import _compute_sim_metrics

def test_metrics_schema():
    df = pd.DataFrame([
        {"prize": 30.0, "finish": 1, "dup_count": 1},
        {"prize": 0.0, "finish": 2, "dup_count": 1},
    ])
    metrics = _compute_sim_metrics(df)
    schema = load_schema(Path("pipeline/schemas/sim_metrics.schema.yaml"))
    validate_obj(schema, metrics, schemas_root=Path("pipeline/schemas"))
