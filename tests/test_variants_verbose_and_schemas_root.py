from __future__ import annotations

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


def test_verbose_prints_lineups_path(capsys, tmp_path: Path, monkeypatch):
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

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_ok)

    argv = [
        "--slate-id",
        slate_id,
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--input",
        str(opt_path),
        "--verbose",
    ]
    rc = var.main(argv)
    assert rc == 0
    err = capsys.readouterr().err
    assert "[variants] input=" in err and "variants=" in err
    assert str(opt_path) in err


def test_schemas_root_robust(tmp_path: Path, monkeypatch):
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

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_ok)

    argv = [
        "--slate-id",
        slate_id,
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--input",
        str(opt_path),
    ]
    rc = var.main(argv)
    assert rc == 0
