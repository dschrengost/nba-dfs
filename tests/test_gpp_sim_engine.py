from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from processes.gpp_sim.engine import run_sim
from processes.gpp_sim.io_schemas import load_contest, load_lineups

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gpp"


def test_engine_basic() -> None:
    lineups = load_lineups(FIXTURE_DIR / "lineups.csv")
    contest = load_contest(FIXTURE_DIR / "contest.csv")
    results, summary = run_sim(lineups, contest)
    assert summary["entries"] == 4
    assert summary["unique_lineups"] == 2
    assert math.isclose(summary["total_prizes"], 80.0)
    assert math.isclose(summary["roi"], 1.0)
    assert results.shape[0] == 2
    dup = dict(zip(results["lineup_id"], results["dup_count"], strict=True))
    assert dup["L1"] == 3
    assert summary["dup"]["max"] == 3


def test_engine_missing_buy_in() -> None:
    lineups = load_lineups(FIXTURE_DIR / "lineups.csv")
    contest = load_contest(FIXTURE_DIR / "contest_no_buyin.csv")
    _results, summary = run_sim(lineups, contest)
    assert summary["total_fees"] == 0.0
    assert summary["roi"] == 0.0


def test_lineups_missing_column(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("lineup_id,player_ids\nL1,p1|p2\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_lineups(bad)
