from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from processes.variants import adapter as var


def _stub_ok(parent_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    base = parent_df.iloc[0]
    return [
        {
            "variant_id": "V1",
            "parent_lineup_id": str(base["lineup_id"]),
            "players": list(base["players"]),
            "variant_params": {},
        }
    ]


def test_run_id_determinism(tmp_path: Path, monkeypatch):
    class FakeDT:
        @staticmethod
        def now(tz=None):
            return datetime(2025, 11, 1, 18, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(var, "datetime", FakeDT)

    slate_id = "20251101_NBA"
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    players = [f"p{i}" for i in range(8)]
    base = {
        "run_id": "rid",
        "lineup_id": "L1",
        "players": players,
        "dk_positions_filled": dk_pos,
        "total_salary": 48000,
        "proj_fp": 200.0,
        "export_csv_row": var.export_csv_row(players, dk_pos),
    }
    opt_path = tmp_path / "opt.parquet"
    pd.DataFrame([base]).to_parquet(opt_path)

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_ok)

    out_root = tmp_path / "out"
    r1 = var.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=opt_path,
    )
    r2 = var.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=opt_path,
    )
    assert r1["run_id"] == r2["run_id"]

    r3 = var.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=None,
        seed=2,
        out_root=out_root,
        tag=None,
        input_path=opt_path,
    )
    assert r1["run_id"] != r3["run_id"]
