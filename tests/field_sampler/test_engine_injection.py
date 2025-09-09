from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from processes.field_sampler import engine
from processes.field_sampler import injection_model as fs


def test_engine_smoke() -> None:
    catalog = pd.DataFrame([{"players": [f"p{i}" for i in range(8)]}])
    entrants1, _ = engine.run_sampler(catalog, {"field_size": 1}, seed=1)
    entrants2, _ = engine.run_sampler(catalog, {"field_size": 1}, seed=1)
    assert entrants1 == entrants2
    assert entrants1[0]["players"] == [f"p{i}" for i in range(8)]


def test_injection_model(tmp_path: Path, monkeypatch) -> None:
    projections = pd.DataFrame(
        [
            {"player_id": f"p{i}", "team": "A", "positions": "PG", "salary": 1000 * i}
            for i in range(1, 9)
        ]
    )
    vc = pd.DataFrame([{"players": [f"p{i}" for i in range(1, 9)]}])
    monkeypatch.chdir(tmp_path)
    metrics = fs.build_field(projections, field_size=1, seed=1, slate_id="SL", variant_catalog=vc)
    base = tmp_path / "artifacts" / "field_base.jsonl"
    merged = tmp_path / "artifacts" / "field_merged.jsonl"
    assert base.exists() and merged.exists()
    merged_rows = [json.loads(line) for line in merged.read_text().splitlines()]
    assert metrics["field_base_count"] == 1
    assert metrics["field_merged_count"] == 2
    assert merged_rows[1]["source"] == "injected"
