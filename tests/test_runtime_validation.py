from __future__ import annotations

import shutil
from pathlib import Path

import yaml


def test_runtime_validation_blocks_on_schema_mismatch(tmp_path: Path) -> None:
    # Prepare a schemas_root copy that rejects 'ingest' run_type
    # by removing it from the RunTypeEnum list
    schemas_src = Path("pipeline/schemas")
    schemas_dst = tmp_path / "schemas_bad"
    shutil.copytree(schemas_src, schemas_dst)

    # Overwrite common.types.yaml to drop 'ingest' from RunTypeEnum
    # using a robust YAML edit instead of string replacement
    common_path = schemas_dst / "common.types.yaml"
    common_schema = yaml.safe_load(common_path.read_text())
    enum_path = ["definitions", "RunTypeEnum", "enum"]
    cursor = common_schema
    for key in enum_path[:-1]:
        cursor = cursor[key]
    enum_list = list(cursor.get(enum_path[-1], []))
    if "ingest" in enum_list:
        enum_list.remove("ingest")
        cursor[enum_path[-1]] = enum_list
        common_path.write_text(yaml.safe_dump(common_schema, sort_keys=False))

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
            "--schemas-root",
            str(schemas_dst),
        ]
    )
    assert rc != 0, "Expected non-zero exit on validation failure"

    # Ensure nothing was written (no manifest, no parquet outputs)
    assert not (out_root / "runs").exists()
    assert not (out_root / "registry").exists()
    assert not (out_root / "projections").exists()
    assert not (out_root / "reference").exists()
