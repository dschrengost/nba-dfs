from __future__ import annotations

from pathlib import Path

import json
import pandas as pd


def test_ingest_cli_smoke(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    projections = Path("tests/fixtures/projections_sourceA.csv")
    players = Path("tests/fixtures/player_ids.csv")
    mapping = Path("pipeline/ingest/mappings/example_source.yaml")

    # run CLI
    from pipeline.ingest.cli import main  # import here to avoid package issues

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
            "--tag",
            "PRP-1",
        ]
    )
    assert rc == 0

    # Check artifacts exist
    players_out = out_root / "reference/players.parquet"
    raw_dir = out_root / "projections/raw"
    norm_dir = out_root / "projections/normalized"
    registry = out_root / "registry/runs.parquet"
    assert players_out.exists()
    assert list(raw_dir.glob("*.parquet")), "raw parquet not written"
    norm_files = list(norm_dir.glob("*.parquet"))
    assert norm_files, "normalized parquet not written"
    assert registry.exists()

    # Validate normalized columns
    df_norm = pd.read_parquet(norm_files[0])
    expected_cols = {
        "slate_id",
        "source",
        "dk_player_id",
        "name",
        "team",
        "pos",
        "salary",
        "minutes",
        "proj_fp",
        "updated_ts",
        "lineage",
    }
    assert expected_cols.issubset(set(df_norm.columns))

    # Manifest JSON exists
    run_dirs = list((out_root / "runs/ingest").glob("*"))
    assert run_dirs, "run directory not created"
    manifest_path = run_dirs[0] / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"] and manifest["schema_version"] == "0.2.0"
