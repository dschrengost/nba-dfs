from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.optimizer import adapter as opt

_CAPTURED: dict[str, Any] = {}


def _stub_capture(
    df: pd.DataFrame, constraints: dict[str, Any], seed: int, site: str, engine: str
):
    # Capture constraints for assertion; return one trivial lineup
    _CAPTURED.clear()
    _CAPTURED.update(constraints)
    dk_pos = [
        {"slot": s, "position": s}
        for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]
    l = {
        "players": list(df["player_id"].head(8)),
        "dk_positions_filled": dk_pos,
        "total_salary": int(df["salary"].head(8).sum()),
        "proj_fp": float(df["proj_fp"].head(8).sum()),
    }
    return [l]


def test_ownership_penalty_passthrough(monkeypatch, tmp_path: Path):
    # Minimal projections
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

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_capture)

    config = {
        "num_lineups": 1,
        "ownership_penalty": {"enabled": True, "mode": "sigmoid", "lambda": 1.2},
    }
    config_path = tmp_path / "cfg.json"
    config_path.write_text(json_dumps(config), encoding="utf-8")

    opt.run_adapter(
        slate_id=slate_id,
        site="DK",
        config_path=config_path,
        config_kv=None,
        engine="cbc",
        seed=1,
        out_root=tmp_path / "out",
        tag=None,
        in_root=tmp_path,
        input_path=None,
    )

    assert "ownership_penalty" in _CAPTURED
    assert _CAPTURED["ownership_penalty"]["enabled"] is True


def json_dumps(obj: dict[str, Any]) -> str:
    import json

    return json.dumps(obj)
