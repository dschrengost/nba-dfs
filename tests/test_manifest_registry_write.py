from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def test_manifest_and_registry(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    projections = Path("tests/fixtures/projections_sourceA.csv")
    players = Path("tests/fixtures/player_ids.csv")
    mapping = Path("pipeline/ingest/mappings/example_source.yaml")

    from pipeline.ingest.cli import main

    rc = main(
        [
            "--slate-id",
            "20251101_NBA",
            "--source",
            "primary",
            "--projections",
            str(projections),
            "--player-ids",
            str(players),
            "--mapping",
            str(mapping),
            "--out-root",
            str(out_root),
        ]
    )
    assert rc == 0

    run_dirs = list((out_root / "runs/ingest").glob("*"))
    assert run_dirs
    manifest_path = run_dirs[0] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"] and manifest["run_type"] == "ingest"
    assert any(i.get("content_sha256") for i in manifest.get("inputs", []))

    registry = out_root / "registry/runs.parquet"
    assert registry.exists()
    df = pd.read_parquet(registry)
    assert not df.empty
    assert set(["run_id", "run_type", "slate_id", "status"]).issubset(df.columns)
    assert (df["run_type"] == "ingest").all()
