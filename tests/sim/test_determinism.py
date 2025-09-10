import pandas as pd
from processes.orchestrator.core import _compute_sim_metrics


def test_determinism():
    df = pd.DataFrame([
        {"prize": 20.0, "finish": 1, "dup_count": 2},
        {"prize": 0.0, "finish": 3, "dup_count": 1},
    ])
    m1 = _compute_sim_metrics(df)
    m2 = _compute_sim_metrics(df.sample(frac=1, random_state=42).reset_index(drop=True))
    assert m1 == m2
