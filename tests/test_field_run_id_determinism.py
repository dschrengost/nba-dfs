from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _stub_ok(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    row = catalog_df.iloc[0]
    players = list(row["players"]) if "players" in row else [f"p{i}" for i in range(8)]
    return [
        {
            "origin": "variant",
            "variant_id": str(row.get("variant_id", "V1")),
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
    ]


def test_run_id_determinism(tmp_path: Path, monkeypatch):
    class FakeDT:
        @staticmethod
        def now(tz=None):
            return datetime(2025, 11, 1, 18, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(field, "datetime", FakeDT)

    vc = pd.DataFrame(
        [
            {
                "run_id": "rid_var",
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
    )
    cat_path = tmp_path / "variant_catalog.parquet"
    vc.to_parquet(cat_path)

    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_ok)

    out_root = tmp_path / "out"
    r1 = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=cat_path,
    )
    r2 = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag=None,
        input_path=cat_path,
    )
    assert r1["run_id"] == r2["run_id"]

    r3 = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=None,
        seed=2,
        out_root=out_root,
        tag=None,
        input_path=cat_path,
    )
    assert r1["run_id"] != r3["run_id"]
