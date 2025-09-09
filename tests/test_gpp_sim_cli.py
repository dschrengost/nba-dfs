from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gpp"


def test_cli_smoke(tmp_path: Path) -> None:
    out = tmp_path / "runs"
    cmd = [
        sys.executable,
        "-m",
        "processes.gpp_sim",
        "--lineups",
        str(FIXTURE_DIR / "lineups.csv"),
        "--contest",
        str(FIXTURE_DIR / "contest.csv"),
        "--outdir",
        str(out),
    ]
    subprocess.check_call(cmd)
    run_dirs = list(out.iterdir())
    assert run_dirs, "run dir not created"
    run_dir = run_dirs[0]
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["entries"] == 4
    res_path = run_dir / "sim_results.parquet"
    assert res_path.exists()
    df = pd.read_parquet(res_path)
    assert "lineup_id" in df.columns
