from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _stub_bad_sampler(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    # Return a single entrant with only 7 players to trigger fail-fast
    players = [f"p{i}" for i in range(7)]
    return [
        {
            "origin": "variant",
            "players": players,
            "export_csv_row": ",".join(
                f"{s} p{i}" for i, s in enumerate(["PG", "SG", "SF", "PF", "C", "G", "F"], start=0)
            ),
        }
    ]


def test_failfast_blocks_writes(tmp_path: Path, monkeypatch):
    # Minimal catalog input (not actually used by stub)
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

    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_bad_sampler)

    out_root = tmp_path / "out"
    try:
        field.run_adapter(
            slate_id="20251101_NBA",
            config_path=None,
            config_kv=None,
            seed=1,
            out_root=out_root,
            tag=None,
            input_path=cat_path,
        )
        raise AssertionError("Expected ValueError due to invalid entrant")
    except ValueError:
        pass

    # No run directory should be created
    field_runs = list((out_root / "runs" / "field").glob("*"))
    assert not field_runs
