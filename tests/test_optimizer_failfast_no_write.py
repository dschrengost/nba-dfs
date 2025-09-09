from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from processes.optimizer import adapter as opt


def _stub_bad_lineup(
    df: pd.DataFrame, constraints: dict[str, Any], seed: int, site: str, engine: str
):
    # Return a single lineup with 7 players (invalid)
    players = list(df["player_id"].head(7))
    dk_pos = [
        {"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F"]  # missing UTIL
    ]
    return [
        {
            "players": players,
            "dk_positions_filled": dk_pos,
            "total_salary": int(df["salary"].head(7).sum()),
            "proj_fp": float(df["proj_fp"].head(7).sum()),
        }
    ]


def test_failfast_no_write(tmp_path: Path, monkeypatch):
    slate_id = "20251101_NBA"
    proj_path = tmp_path / "projections" / "normalized" / f"{slate_id}.parquet"
    proj_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "slate_id": [slate_id] * 8,
            "dk_player_id": [f"p{i}" for i in range(8)],
            "pos": ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
            "salary": [5000] * 8,
            "proj_fp": [20.0] * 8,
        }
    )
    df.to_parquet(proj_path)

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_bad_lineup)

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError):
        opt.run_adapter(
            slate_id=slate_id,
            site="DK",
            config_path=None,
            config_kv=None,
            engine="cbc",
            seed=1,
            out_root=out_root,
            tag=None,
            in_root=tmp_path,
            input_path=None,
        )

    # Ensure no files were written
    registry = out_root / "registry" / "runs.parquet"
    assert not registry.exists()
    # There may be a runs dir created, but no artifacts should exist
    runs_root = out_root / "runs" / "optimizer"
    if runs_root.exists():
        for run_dir in runs_root.iterdir():
            assert not (run_dir / "manifest.json").exists()
            assert not (run_dir / "artifacts" / "lineups.parquet").exists()
            assert not (run_dir / "artifacts" / "metrics.parquet").exists()
