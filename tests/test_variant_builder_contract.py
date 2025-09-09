from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.variant_builder import BuildParams, build_variant_catalog


def _make_player_pool(path: Path) -> Path:
    df = pd.DataFrame(
        {
            "player_id": [f"p{i}" for i in range(8)],
            "team": [f"T{i}" for i in range(8)],
            "salary": [6000] * 8,
            "positions": [
                "PG",
                "SG",
                "SF",
                "PF",
                "C",
                "SG",
                "PF",
                "C",
            ],
        }
    )
    df.to_csv(path, index=False)
    return path


def _write_optimizer_run(path: Path, lineup: list[tuple[str, str]]) -> Path:
    row = {"lineup": lineup}
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return path


def test_build_variant_catalog(tmp_path: Path) -> None:
    pool_path = _make_player_pool(tmp_path / "players.csv")
    lineup = [
        ("PG", "p0"),
        ("SG", "p1"),
        ("SF", "p2"),
        ("PF", "p3"),
        ("C", "p4"),
        ("G", "p5"),
        ("F", "p6"),
        ("UTIL", "p7"),
    ]
    opt_path = _write_optimizer_run(tmp_path / "optimizer_run.jsonl", lineup)
    out_path = tmp_path / "variant_catalog.jsonl"

    params = BuildParams(
        optimizer_run=opt_path,
        player_pool=pool_path,
        output_path=out_path,
        slate_id="20250101_NBA",
    )
    build_variant_catalog(params)

    assert out_path.exists()
    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["lineup"] == [f"p{i}" for i in range(8)]
    assert rec["salary_total"] == 48000
    assert rec["teams"] == [f"T{i}" for i in range(8)]
    assert rec["valid"] is True
    assert rec["tags"] == []
    # created_at is ISO 8601 with Z suffix
    datetime.fromisoformat(rec["created_at"].replace("Z", "+00:00"))
    assert rec["slate_id"] == "20250101_NBA"
    assert rec["site"] == "DK"
    assert rec["run_id"]
    assert rec["source_branch"]


def test_invalid_lineup_raises(tmp_path: Path) -> None:
    pool_path = _make_player_pool(tmp_path / "players.csv")
    lineup = [
        ("PG", "p0"),
        ("SG", "p0"),  # duplicate player should fail
        ("SF", "p2"),
        ("PF", "p3"),
        ("C", "p4"),
        ("G", "p5"),
        ("F", "p6"),
        ("UTIL", "p7"),
    ]
    opt_path = _write_optimizer_run(tmp_path / "optimizer_run.jsonl", lineup)
    out_path = tmp_path / "variant_catalog.jsonl"

    params = BuildParams(
        optimizer_run=opt_path,
        player_pool=pool_path,
        output_path=out_path,
        slate_id="20250101_NBA",
    )
    with pytest.raises(ValueError, match="Invalid lineup"):
        build_variant_catalog(params)


def test_build_variant_catalog_reorders_slots(tmp_path: Path) -> None:
    pool_path = _make_player_pool(tmp_path / "players.csv")
    lineup = [
        ("SG", "p1"),
        ("PG", "p0"),
        ("SF", "p2"),
        ("PF", "p3"),
        ("C", "p4"),
        ("G", "p5"),
        ("F", "p6"),
        ("UTIL", "p7"),
    ]
    opt_path = _write_optimizer_run(tmp_path / "optimizer_run.jsonl", lineup)
    out_path = tmp_path / "variant_catalog.jsonl"

    params = BuildParams(
        optimizer_run=opt_path,
        player_pool=pool_path,
        output_path=out_path,
        slate_id="20250101_NBA",
    )
    build_variant_catalog(params)

    rec = json.loads(out_path.read_text().strip())
    assert rec["lineup"] == [f"p{i}" for i in range(8)]
