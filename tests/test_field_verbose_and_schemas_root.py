from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _stub_ok(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    players = [f"p{i}" for i in range(8)]
    return [
        {
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
    ]


def test_verbose_prints_inputs(capsys, tmp_path: Path, monkeypatch):
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
                    for i, s in enumerate(
                        ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"], start=0
                    )
                ),
            }
        ]
    ).to_parquet(cat_path)

    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_ok)

    argv = [
        "--slate-id",
        "20251101_NBA",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--input",
        str(cat_path),
        "--verbose",
    ]
    rc = field.main(argv)
    assert rc == 0
    err = capsys.readouterr().err
    assert "[field] input=" in err and "entrants=" in err
    assert str(cat_path) in err


def test_schemas_root_override(tmp_path: Path, monkeypatch):
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
                    for i, s in enumerate(
                        ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"], start=0
                    )
                ),
            }
        ]
    ).to_parquet(cat_path)

    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_ok)

    argv = [
        "--slate-id",
        "20251101_NBA",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--input",
        str(cat_path),
        "--schemas-root",
        str(Path("pipeline/schemas")),
    ]
    rc = field.main(argv)
    assert rc == 0
