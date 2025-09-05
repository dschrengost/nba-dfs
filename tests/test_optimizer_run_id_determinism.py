from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from processes.optimizer import adapter as opt


def _stub_ok(
    df: pd.DataFrame, constraints: dict[str, Any], seed: int, site: str, engine: str
):
    slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    l = {
        "players": list(df["player_id"].head(8)),
        "dk_positions_filled": [{"slot": s, "position": s} for s in slots],
        "total_salary": int(df["salary"].head(8).sum()),
        "proj_fp": float(df["proj_fp"].head(8).sum()),
    }
    return [l]


def test_run_id_determinism(tmp_path: Path, monkeypatch):
    # Freeze time
    class FakeDT:
        @staticmethod
        def now(tz=None):
            return datetime(2025, 11, 1, 18, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(opt, "datetime", FakeDT)

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

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_ok)

    out_root = tmp_path / "out"
    r1 = opt.run_adapter(
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
    r2 = opt.run_adapter(
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
    assert (
        r1["run_id"] == r2["run_id"]
    ), "Run IDs should be deterministic for same inputs + frozen time"

    r3 = opt.run_adapter(
        slate_id=slate_id,
        site="DK",
        config_path=None,
        config_kv=None,
        engine="cbc",
        seed=2,  # different seed
        out_root=out_root,
        tag=None,
        in_root=tmp_path,
        input_path=None,
    )
    assert r1["run_id"] != r3["run_id"], "Run ID should change when seed changes"
