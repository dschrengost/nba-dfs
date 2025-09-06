from __future__ import annotations

from pathlib import Path

import pytest

from processes.metrics import adapter as metrics


def test_metrics_failfast_missing_sim_results(tmp_path: Path):
    # Simulate a sim run directory without artifacts
    out_root = tmp_path / "out"
    missing_run_id = "20990101_000000_deadbeef"
    run_dir = out_root / "runs" / "sim" / missing_run_id
    (run_dir).mkdir(parents=True, exist_ok=True)
    # No sim_results written
    with pytest.raises(FileNotFoundError):
        metrics.run_adapter(from_sim_run=missing_run_id, out_root=out_root)

