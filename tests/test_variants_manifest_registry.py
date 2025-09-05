from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from processes.variants import adapter as var


def _stub_run(parent_df, knobs: dict[str, Any], seed: int):
    base = parent_df.iloc[0]
    return [
        {
            "variant_id": "V1",
            "parent_lineup_id": str(base["lineup_id"]),
            "players": list(base["players"]),
            "variant_params": {},
        }
    ]


def test_manifest_and_registry_written(monkeypatch, tmp_path: Path):
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

    monkeypatch.setattr(var, "_load_variant", lambda: _stub_run)

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    result = var.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=opt_path,
    )

    manifest_path = Path(result["manifest_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_type"] == "variants"
    assert any(o["kind"] == "variant_catalog" for o in manifest.get("outputs", []))
    # Input role should reflect optimizer lineups
    assert manifest["inputs"][0]["role"] == "optimizer_lineups"

    reg_df = pd.read_parquet(out_root / "registry" / "runs.parquet")
    row = reg_df.iloc[-1]
    assert row["run_type"] == "variants"
    assert str(result["catalog_path"]) in row["primary_outputs"][0]
