from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from processes.optimizer import adapter as opt


def _stub_run(df: pd.DataFrame, constraints: dict[str, Any], seed: int, site: str, engine: str):
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    lineup = {
        "players": list(df["player_id"].head(8)),
        "dk_positions_filled": dk_pos,
        "total_salary": int(df["salary"].head(8).sum()),
        "proj_fp": float(df["proj_fp"].head(8).sum()),
    }
    return [lineup]


def test_manifest_and_registry_written(monkeypatch, tmp_path: Path):
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

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_run)

    out_root = tmp_path / "out"
    result = opt.run_adapter(
        slate_id=slate_id,
        site="DK",
        config_path=None,
        config_kv=None,
        engine="cbc",
        seed=1,
        out_root=out_root,
        tag="tag1",
        in_root=tmp_path,
        input_path=None,
    )

    # Load and inspect manifest
    manifest_path = Path(result["manifest_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_type"] == "optimizer"
    assert manifest["schema_version"]
    assert manifest["created_ts"].endswith("Z")
    assert any(o["kind"] == "optimizer_lineups" for o in manifest.get("outputs", []))

    # Registry row
    reg_df = pd.read_parquet(out_root / "registry" / "runs.parquet")
    assert (reg_df["run_id"] == result["run_id"]).any()
