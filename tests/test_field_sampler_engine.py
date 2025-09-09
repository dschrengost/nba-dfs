import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest

from field_sampler.engine import SamplerEngine
from validators.lineup_rules import DK_SLOTS_ORDER, LineupValidator

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


def _read_base(path: Path) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], json.loads(line)) for line in path.read_text().splitlines()]


def test_golden_mini_slate(tmp_path: Path) -> None:
    projections = pd.read_csv(Path("tests/fixtures/mini_slate.csv"))
    eng = SamplerEngine(projections, seed=1, out_dir=tmp_path)
    eng.generate(1)
    rows = _read_base(tmp_path / "field_base.jsonl")
    assert rows[0]["players"] == [
        "p1",
        "p10",
        "p7",
        "p4",
        "p8",
        "p6",
        "p11",
        "p12",
    ]
    validator = LineupValidator()
    lineup = list(
        zip(
            DK_SLOTS_ORDER,
            cast(list[str], rows[0]["players"]),
            strict=False,
        )
    )
    assert validator.validate(lineup, projections)


def test_salary_and_team_limits(tmp_path: Path) -> None:
    projections = pd.read_csv(Path("tests/fixtures/mini_slate.csv"))
    eng = SamplerEngine(projections, seed=2, out_dir=tmp_path)
    eng.generate(3)
    rows = _read_base(tmp_path / "field_base.jsonl")
    validator = LineupValidator()
    for row in rows:
        lineup = list(
            zip(
                DK_SLOTS_ORDER,
                cast(list[str], row["players"]),
                strict=False,
            )
        )
        assert validator.validate(lineup, projections)


def test_salary_violation_rejected(tmp_path: Path) -> None:
    projections = pd.read_csv(Path("tests/fixtures/mini_slate.csv"))
    extra = pd.DataFrame([{"player_id": "bad", "team": "Z", "positions": "PG", "salary": 60000}])
    projections = pd.concat([projections, extra], ignore_index=True)
    eng = SamplerEngine(projections, seed=3, out_dir=tmp_path)
    eng.generate(2)
    rows = _read_base(tmp_path / "field_base.jsonl")
    for row in rows:
        assert "bad" not in cast(list[str], row["players"])


@pytest.mark.parametrize("drop", [True, False])  # type: ignore[misc]
def test_uniform_weights_without_ownership(tmp_path: Path, drop: bool) -> None:
    projections = pd.read_csv(Path("tests/fixtures/mini_slate.csv"))
    if drop:
        projections = projections.drop(columns=["ownership"])
    else:
        projections["ownership"] = 0.0
    eng = SamplerEngine(projections, seed=9, out_dir=tmp_path)
    meta = eng.generate(1)
    rows = _read_base(tmp_path / "field_base.jsonl")
    assert meta["field_base_count"] == 1
    assert len(rows) == 1


@settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])  # type: ignore[misc]
@given(st.integers(min_value=12, max_value=18))  # type: ignore[misc]
def test_property_valid_lineups(tmp_path: Path, n_players: int) -> None:
    ids = [f"p{i}" for i in range(n_players)]
    teams = [f"T{i%3}" for i in range(n_players)]
    positions = ["PG", "SG", "SF", "PF", "C", "PG/SG", "SF/PF"]
    rows = []
    for pid, team in zip(ids, teams, strict=False):
        pos = positions[hash(pid) % len(positions)]
        salary = 2000 + (hash(pid) % 8000)
        rows.append(
            {
                "player_id": pid,
                "team": team,
                "positions": pos,
                "salary": salary,
                "ownership": 0.1,
            }
        )
    projections = pd.DataFrame(rows)
    eng = SamplerEngine(projections, seed=0, out_dir=tmp_path)
    meta = eng.generate(5)
    rows = _read_base(tmp_path / "field_base.jsonl")
    validator = LineupValidator()
    valid = 0
    for row in rows:
        lineup = list(
            zip(
                DK_SLOTS_ORDER,
                cast(list[str], row["players"]),
                strict=False,
            )
        )
        if validator.validate(lineup, projections):
            valid += 1
    assert valid == len(rows)
    assert valid / meta["attempts"] >= 0.01
