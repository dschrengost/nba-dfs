from __future__ import annotations

import json
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


def test_manifest_and_registry(tmp_path: Path, monkeypatch):
    # Minimal catalog
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

    out_root = tmp_path / "out"
    res = field.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out_root,
        tag="PRP-4",
        input_path=cat_path,
    )
    run_id = res["run_id"]
    run_dir = out_root / "runs" / "field" / run_id
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["run_type"] == "field" and manifest["run_id"] == run_id
    assert any(i.get("content_sha256") for i in manifest.get("inputs", []))
    # Registry
    reg = pd.read_parquet(out_root / "registry" / "runs.parquet")
    assert (reg["run_type"] == "field").any()
