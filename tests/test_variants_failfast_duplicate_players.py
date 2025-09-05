from __future__ import annotations

# ruff: noqa: I001

from pathlib import Path
import pandas as pd
import pytest

from processes.variants import adapter as var


def _stub_dup(parent_df: pd.DataFrame, knobs, seed: int):
    base = parent_df.iloc[0]
    players = list(base["players"])[:7] + [base["players"][0]]  # duplicate
    return [
        {
            "variant_id": "Vdup",
            "parent_lineup_id": str(base["lineup_id"]),
            "players": players,
            "variant_params": {},
        }
    ]


def test_failfast_duplicate_players(tmp_path: Path, monkeypatch):
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

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_dup)

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
    runs_root = out_root / "runs" / "variants"
    if runs_root.exists():
        for run_dir in runs_root.iterdir():
            assert not (run_dir / "manifest.json").exists()
            assert not (run_dir / "artifacts" / "variant_catalog.parquet").exists()
            assert not (run_dir / "artifacts" / "metrics.parquet").exists()
