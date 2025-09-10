import pandas as pd

from processes.orchestrator.core import _compute_sim_metrics


def test_invariants():
    df = pd.DataFrame(
        [
            {"prize": 2.0, "finish": 1, "dup_count": 1},
            {"prize": 0.0, "finish": 2, "dup_count": 1},
        ]
    )
    metrics = _compute_sim_metrics(df)
    assert abs(metrics["roi"]["mean"]) < 1e-6
    dup = metrics["duplication"]
    assert dup["unique_fraction"] + dup["dup_fraction"] <= 1.0 + 1e-6
    assert dup["dup_bins"] == []
