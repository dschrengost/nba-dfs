from __future__ import annotations

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


def test_verbose_prints_projections(capsys, tmp_path: Path, monkeypatch):
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

    # Invoke CLI main with --verbose
    argv = [
        "--slate-id",
        slate_id,
        "--site",
        "DK",
        "--engine",
        "cbc",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--in-root",
        str(tmp_path),
        "--verbose",
    ]
    rc = opt.main(argv)
    assert rc == 0
    captured = capsys.readouterr()
    assert "[optimizer] projections:" in captured.err
    assert str(proj_path) in captured.err


def test_schemas_root_robust_cwd(tmp_path: Path, monkeypatch):
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

    # Change CWD to a subdir (simulate running from processes/)
    subdir = Path.cwd() / "processes"
    # We don't actually chdir on the real repo; just ensure adapter resolves its own schemas root
    # by passing absolute paths for in/out roots and calling main.
    argv = [
        "--slate-id",
        slate_id,
        "--site",
        "DK",
        "--engine",
        "cbc",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--in-root",
        str(tmp_path),
    ]
    rc = opt.main(argv)
    assert rc == 0
