from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from processes.field_sampler import adapter as field


def _export_row(players: list[str]) -> str:
    slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    return ",".join(f"{s} {p}" for s, p in zip(slots, players, strict=False))


def _stub_run_sampler(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    # Use first two catalog rows to build 2 entrants
    e: list[dict[str, Any]] = []
    for _, row in catalog_df.head(2).iterrows():
        players = list(row["players"])  # 8 DK IDs
        e.append(
            {
                "origin": "variant",
                "variant_id": str(row.get("variant_id", "V")),
                "players": players,
                "export_csv_row": str(row.get("export_csv_row") or _export_row(players)),
                "weight": 1.0,
            }
        )
    return e, {"note": "stub"}


def test_smoke_end_to_end(tmp_path: Path, monkeypatch):
    slate_id = "20251101_NBA"
    # Prepare a tiny variant catalog parquet
    players1 = [f"p{i}" for i in range(8)]
    players2 = [f"p{i}" for i in [0, 2, 3, 4, 5, 6, 7, 1]]
    vc = pd.DataFrame(
        [
            {
                "run_id": "rid_var",
                "variant_id": "V1",
                "parent_lineup_id": "L1",
                "players": players1,
                "variant_params": {"_": None},
                "export_csv_row": _export_row(players1),
            },
            {
                "run_id": "rid_var",
                "variant_id": "V2",
                "parent_lineup_id": "L1",
                "players": players2,
                "variant_params": {"_": None},
                "export_csv_row": _export_row(players2),
            },
        ]
    )
    cat_path = tmp_path / "variant_catalog.parquet"
    vc.to_parquet(cat_path)

    # Monkeypatch sampler loader
    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_run_sampler)

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    # Act
    result = field.run_adapter(
        slate_id=slate_id,
        config_path=None,
        config_kv=["field_size=2"],
        seed=42,
        out_root=out_root,
        tag="PRP-4",
        input_path=cat_path,
    )

    # Assert artifacts
    run_id = result["run_id"]
    run_dir = out_root / "runs" / "field" / run_id
    assert (run_dir / "artifacts" / "field.parquet").exists()
    assert (run_dir / "artifacts" / "metrics.parquet").exists()
    assert (run_dir / "manifest.json").exists()
    # Registry appended
    registry = out_root / "registry" / "runs.parquet"
    assert registry.exists()
    reg_df = pd.read_parquet(registry)
    assert (reg_df["run_type"] == "field").any()
