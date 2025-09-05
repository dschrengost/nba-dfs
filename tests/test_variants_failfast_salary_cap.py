from __future__ import annotations

# ruff: noqa: I001

from pathlib import Path
import pandas as pd
import pytest

from processes.variants import adapter as var


def _stub_overcap(parent_df: pd.DataFrame, knobs, seed: int):
    base = parent_df.iloc[0]
    return [
        {
            "variant_id": "Vcap",
            "parent_lineup_id": str(base["lineup_id"]),
            "players": list(base["players"]),
            "variant_params": {},
            "total_salary": 50001,  # over cap
        }
    ]


def test_failfast_salary_cap(tmp_path: Path, monkeypatch):
    slate_id = "20251101_NBA"
    dk_pos = [
        {"slot": s, "position": s}
        for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]
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

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_overcap)

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError):
        var.run_adapter(
            slate_id=slate_id,
            config_path=None,
            config_kv=None,
            seed=1,
            out_root=out_root,
            tag=None,
            input_path=opt_path,
        )

    registry = out_root / "registry" / "runs.parquet"
    assert not registry.exists()
