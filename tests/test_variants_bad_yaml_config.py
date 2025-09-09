from __future__ import annotations

# ruff: noqa: I001

from pathlib import Path

import pytest

from processes.variants import adapter as var


def test_bad_yaml_config_message(tmp_path: Path):
    slate_id = "20251101_NBA"
    # Prepare minimal valid optimizer lineups file
    import pandas as pd

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

    # Malformed YAML
    bad = tmp_path / "bad.yaml"
    bad.write_text("exposure_targets: [oops\n", encoding="utf-8")

    with pytest.raises(ValueError) as ei:
        var.run_adapter(
            slate_id=slate_id,
            config_path=bad,
            config_kv=None,
            seed=1,
            out_root=tmp_path / "out",
            tag=None,
            input_path=opt_path,
        )

    msg = str(ei.value)
    assert "bad.yaml" in msg
    assert "Failed to parse YAML" in msg
