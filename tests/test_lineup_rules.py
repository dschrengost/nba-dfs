import pandas as pd

from validators.lineup_rules import DK_SLOTS_ORDER, LineupValidator


def _pool() -> pd.DataFrame:
    return pd.DataFrame(
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


def test_valid_lineup_passes() -> None:
    pool = _pool()
    lineup = list(zip(DK_SLOTS_ORDER, [f"p{i}" for i in range(1, 9)], strict=False))
    assert LineupValidator().validate(lineup, pool)


def test_salary_cap_violation_fails() -> None:
    pool = _pool()
    lineup = list(zip(DK_SLOTS_ORDER, [f"p{i}" for i in range(1, 9)], strict=False))
    validator = LineupValidator(salary_cap=40000)
    assert not validator.validate(lineup, pool)


def test_slot_eligibility_violation_fails() -> None:
    pool = _pool()
    players = ["p5", "p2", "p3", "p4", "p1", "p6", "p7", "p8"]
    bad_lineup = list(zip(DK_SLOTS_ORDER, players, strict=False))
    assert not LineupValidator().validate(bad_lineup, pool)
