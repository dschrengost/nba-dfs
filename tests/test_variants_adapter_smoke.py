from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.variants import adapter as var


def _stub_run_variants(parent_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    # Build two simple variants from the first base lineup
    base = parent_df.iloc[0]
    players = list(base["players"])  # 8 players
    # swap last two players for V2
    v1 = {
        "variant_id": "V1",
        "parent_lineup_id": str(base["lineup_id"]),
        "players": players,
        "variant_params": {"randomness": knobs.get("randomness", 0)},
        "total_salary": int(base.get("total_salary", 0)),
        "proj_fp": float(base.get("proj_fp", 0.0)),
    }
    v2_players = players[:-2] + [players[-1], players[-2]]
    v2 = {
        "variant_id": "V2",
        "parent_lineup_id": str(base["lineup_id"]),
        "players": v2_players,
        "variant_params": {"swap": {"out": players[-2], "in": players[-1]}},
        "total_salary": int(base.get("total_salary", 0)),
        "proj_fp": float(base.get("proj_fp", 0.0)),
    }
    return [v1, v2]


def test_smoke_adapter_end_to_end(tmp_path: Path, monkeypatch):
    slate_id = "20251101_NBA"
    # Prepare optimizer lineups parquet
    dk_pos = [
        {"slot": s, "position": s}
        for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]
    players = [f"p{i}" for i in range(8)]
    base = {
        "run_id": "20251101_180000_deadbee",
        "lineup_id": "L1",
        "players": players,
        "dk_positions_filled": dk_pos,
        "total_salary": 49800,
        "proj_fp": 275.0,
        "export_csv_row": var.export_csv_row(players, dk_pos),
    }
    opt_lineups = pd.DataFrame([base])
    opt_dir = tmp_path / "runs" / "optimizer" / "20251101_180000_deadbee" / "artifacts"
    opt_dir.mkdir(parents=True, exist_ok=True)
    opt_path = opt_dir / "lineups.parquet"
    opt_lineups.to_parquet(opt_path)

    # Monkeypatch variant loader
    monkeypatch.setattr(var, "_load_variant", lambda: _stub_run_variants)

    out_root = tmp_path
    result = var.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=["randomness=0.1"],
        seed=42,
        out_root=out_root,
        tag="PRP-3",
        input_path=opt_path,
    )

    run_id = result["run_id"]
    run_dir = out_root / "runs" / "variants" / run_id
    assert (run_dir / "artifacts" / "variant_catalog.parquet").exists()
    assert (run_dir / "artifacts" / "metrics.parquet").exists()
    assert (run_dir / "manifest.json").exists()

    # Registry appended
    registry = out_root / "registry" / "runs.parquet"
    assert registry.exists()
    reg_df = pd.read_parquet(registry)
    assert (reg_df["run_type"] == "variants").any()
