import json
from pathlib import Path

import pandas as pd
import pytest

from processes.field_sampler import injection_model as fs
from validators.lineup_rules import DK_SLOTS_ORDER, LineupValidator


def test_build_field_creates_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projections = pd.DataFrame(
        [
            {"player_id": "p1", "team": "A", "positions": "PG", "salary": 10000},
            {"player_id": "p2", "team": "A", "positions": "SG", "salary": 8000},
            {"player_id": "p3", "team": "B", "positions": "SF", "salary": 7000},
            {"player_id": "p4", "team": "B", "positions": "PF", "salary": 6000},
            {"player_id": "p5", "team": "C", "positions": "C", "salary": 5000},
            {"player_id": "p6", "team": "C", "positions": "PG/SG", "salary": 4000},
            {"player_id": "p7", "team": "D", "positions": "SF/PF", "salary": 3000},
            {"player_id": "p8", "team": "D", "positions": "C", "salary": 2000},
        ]
    )
    variant_catalog = pd.DataFrame([{"players": [f"p{i}" for i in range(1, 9)]}])

    monkeypatch.chdir(tmp_path)
    metrics = fs.build_field(
        projections,
        field_size=1,
        seed=1,
        slate_id="SLATE",
        variant_catalog=variant_catalog,
    )

    base_path = tmp_path / "artifacts" / "field_base.jsonl"
    merged_path = tmp_path / "artifacts" / "field_merged.jsonl"
    metrics_path = tmp_path / "artifacts" / "metrics.json"

    assert base_path.exists()
    assert merged_path.exists()
    assert metrics_path.exists()

    merged = [json.loads(line) for line in merged_path.read_text().splitlines()]

    assert metrics["field_base_count"] == 1
    assert metrics["field_merged_count"] == 2
    assert merged[1]["source"] == "injected"

    pool = projections
    validator = LineupValidator()
    for row in merged:
        lineup = list(zip(DK_SLOTS_ORDER, row["players"], strict=False))
        assert validator.validate(lineup, pool)
