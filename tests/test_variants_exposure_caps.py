from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.variants import adapter as var


def test_exposure_caps_honored_in_knobs(tmp_path: Path, monkeypatch):
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

    captured: dict[str, Any] = {}

    def _stub_variant(parent_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
        captured["knobs"] = knobs
        return [
            {
                "variant_id": "V1",
                "parent_lineup_id": "L1",
                "players": players,
                "variant_params": {},
            }
        ]

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_variant)

    out_root = tmp_path / "out"
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "exposure_targets:\n  player_caps:\n    p1: 0.25\n",
        encoding="utf-8",
    )

    var.run_adapter(
        slate_id=slate_id,
        config_path=cfg_path,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=opt_path,
    )

    assert "exposure_targets" in captured["knobs"]
    assert captured["knobs"]["exposure_targets"]["player_caps"]["p1"] == 0.25
