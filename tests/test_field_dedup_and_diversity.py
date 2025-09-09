from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _stub_diversity(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    # Produce 4 entrants; when diversity high or de-dup true, make unique player sets; else all same
    base_players = [f"p{i}" for i in range(8)]

    def row(players: list[str]) -> dict[str, Any]:
        return {
            "origin": "variant",
            "players": players,
            "export_csv_row": ",".join(
                f"{s} {p}"
                for s, p in zip(
                    ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
                    players,
                    strict=False,
                )
            ),
        }

    unique = knobs.get("de-dup") or (knobs.get("diversity", 0.0) or 0.0) >= 0.5
    if unique:
        entrants = []
        for i in range(4):
            players = list(base_players)
            players[-1] = f"x{i}"  # ensure distinct set
            entrants.append(row(players))
    else:
        entrants = [row(base_players) for _ in range(4)]
    return entrants


def test_dedup_and_diversity_metric(tmp_path: Path, monkeypatch):
    cat_path = tmp_path / "vc.parquet"
    pd.DataFrame(
        [
            {
                "run_id": "rid",
                "variant_id": "V1",
                "parent_lineup_id": "L1",
                "players": [f"p{i}" for i in range(8)],
                "variant_params": {"_": None},
                "export_csv_row": ",".join(
                    f"{s} p{i}"
                    for i, s in enumerate(["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"], start=0)
                ),
            }
        ]
    ).to_parquet(cat_path)

    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_diversity)

    out_root = tmp_path / "out"
    # Low diversity → higher duplication_risk
    res_low = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=["diversity=0.0"],
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=cat_path,
    )
    low_metrics = pd.read_parquet(Path(res_low["metrics_path"]))
    low_risk = float(low_metrics.iloc[0].get("duplication_risk", 0.0))

    # High diversity → lower duplication_risk
    res_high = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=["diversity=0.9"],
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=cat_path,
    )
    high_metrics = pd.read_parquet(Path(res_high["metrics_path"]))
    high_risk = float(high_metrics.iloc[0].get("duplication_risk", 0.0))

    assert high_risk < low_risk
