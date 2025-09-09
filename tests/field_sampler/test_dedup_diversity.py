from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _export_row(players: list[str]) -> str:
    slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    return ",".join(f"{s} {p}" for s, p in zip(slots, players, strict=False))


def _stub_diversity(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    base = [f"p{i}" for i in range(8)]

    def mk(players: list[str]) -> dict[str, Any]:
        return {"origin": "variant", "players": players, "export_csv_row": _export_row(players)}

    unique = knobs.get("de-dup") or (knobs.get("diversity", 0.0) or 0.0) >= 0.5
    if unique:
        entrants = []
        for i in range(4):
            players = list(base)
            players[-1] = f"x{i}"
            entrants.append(mk(players))
    else:
        entrants = [mk(base) for _ in range(4)]
    return entrants


def test_dedup_and_diversity_metric(tmp_path: Path, monkeypatch) -> None:
    cat_path = tmp_path / "vc.parquet"
    pd.DataFrame([{"players": [f"p{i}" for i in range(8)]}]).to_parquet(cat_path)
    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_diversity)
    out = tmp_path / "out"
    low = field.run_adapter(
        slate_id="S",
        config_path=None,
        config_kv=["diversity=0"],
        seed=1,
        out_root=out,
        tag=None,
        input_path=cat_path,
    )
    high = field.run_adapter(
        slate_id="S",
        config_path=None,
        config_kv=["diversity=1"],
        seed=1,
        out_root=out,
        tag=None,
        input_path=cat_path,
    )
    low_risk = float(
        pd.read_parquet(Path(low["metrics_path"])).iloc[0].get("duplication_risk", 0.0)
    )
    high_risk = float(
        pd.read_parquet(Path(high["metrics_path"])).iloc[0].get("duplication_risk", 0.0)
    )
    assert high_risk < low_risk
