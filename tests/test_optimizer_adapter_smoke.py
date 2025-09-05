from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.optimizer import adapter as opt


def _stub_run_optimizer(
    df: pd.DataFrame, constraints: dict[str, Any], seed: int, site: str, engine: str
):
    # Produce 2 trivial lineups using the first 8 players twice, swapping UTIL
    players = list(df["player_id"].head(8))
    dk_pos = [
        {"slot": s, "position": s}
        for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]
    l1 = {
        "players": players,
        "dk_positions_filled": dk_pos,
        "total_salary": int(df["salary"].head(8).sum()),
        "proj_fp": float(df["proj_fp"].head(8).sum()),
    }
    l2_players = players[-1:] + players[:-1]
    l2 = {
        "players": l2_players,
        "dk_positions_filled": dk_pos,
        "total_salary": int(df["salary"].head(8).sum()),
        "proj_fp": float(df["proj_fp"].head(8).sum()),
    }
    return [l1, l2], {"note": "stub"}


def test_smoke_adapter_end_to_end(tmp_path: Path, monkeypatch):
    # Arrange minimal projections
    slate_id = "20251101_NBA"
    proj_dir = tmp_path / "projections" / "normalized"
    proj_dir.mkdir(parents=True, exist_ok=True)
    proj_path = proj_dir / f"{slate_id}.parquet"
    df = pd.DataFrame(
        {
            "slate_id": [slate_id] * 8,
            "dk_player_id": [f"p{i}" for i in range(8)],
            "pos": ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
            "salary": [5000, 5500, 6000, 5800, 6200, 5200, 5100, 5000],
            "proj_fp": [30.0, 32.0, 28.0, 27.0, 35.0, 25.0, 24.5, 22.0],
        }
    )
    df.to_parquet(proj_path)

    # Monkeypatch optimizer loader
    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_run_optimizer)

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    # Act
    result = opt.run_adapter(
        slate_id=slate_id,
        site="DK",
        config_path=None,
        config_kv=["num_lineups=2"],
        engine="cbc",
        seed=42,
        out_root=out_root,
        tag="PRP-2",
        in_root=tmp_path,
        input_path=None,
    )

    # Assert artifacts
    run_id = result["run_id"]
    run_dir = out_root / "runs" / "optimizer" / run_id
    assert (run_dir / "artifacts" / "lineups.parquet").exists()
    assert (run_dir / "artifacts" / "metrics.parquet").exists()
    assert (run_dir / "manifest.json").exists()
    # Registry appended
    registry = out_root / "registry" / "runs.parquet"
    assert registry.exists()
    reg_df = pd.read_parquet(registry)
    assert (reg_df["run_id"] == run_id).any()
