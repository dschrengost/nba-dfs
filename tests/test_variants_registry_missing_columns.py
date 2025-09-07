from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from processes.variants import adapter as var


def _stub_ok(parent_df: pd.DataFrame, knobs, seed: int):
    base = parent_df.iloc[0]
    return [
        {
            "variant_id": "V1",
            "parent_lineup_id": str(base["lineup_id"]),
            "players": list(base["players"]),
            "variant_params": {},
        }
    ]


def test_registry_missing_columns_error(tmp_path: Path, monkeypatch):
    slate_id = "20251101_NBA"

    # Prepare optimizer lineups file (to be selected via registry once fixed)
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
    opt_dir = tmp_path / "runs" / "optimizer" / "rid" / "artifacts"
    opt_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([base]).to_parquet(opt_dir / "lineups.parquet")

    # Create malformed registry missing created_ts
    reg = pd.DataFrame(
        [
            {
                "run_id": "rid",
                "run_type": "optimizer",
                "slate_id": slate_id,
                # missing created_ts
                "primary_outputs": [str(opt_dir / "lineups.parquet")],
            }
        ]
    )
    reg_path = tmp_path / "out" / "registry" / "runs.parquet"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg.to_parquet(reg_path)

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_ok)

    with pytest.raises(ValueError):
        var.run_adapter(
            slate_id=slate_id,
            config_path=None,
            config_kv=None,
            seed=1,
            out_root=tmp_path / "out",
            tag=None,
            input_path=None,
            from_run=None,
        )
