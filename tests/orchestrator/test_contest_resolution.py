# ruff: noqa: I001
from pathlib import Path
import pytest
from processes.orchestrator.core import _resolve_contest_input

pytestmark = pytest.mark.smoke


def test_resolve_contest_from_identifier(tmp_path: Path) -> None:
    contests_dir = tmp_path / "contests" / "MY_CONTEST"
    contests_dir.mkdir(parents=True)
    contest_file = contests_dir / "contest_structure.csv"
    contest_file.write_text("rank_start,rank_end,prize\n1,1,10\n", encoding="utf-8")
    contest_path, contest_dir = _resolve_contest_input("MY_CONTEST", tmp_path)
    assert contest_path is None
    assert contest_dir == contests_dir


def test_resolve_contest_from_path(tmp_path: Path) -> None:
    contest_file = tmp_path / "contest.json"
    contest_file.write_text("{}", encoding="utf-8")
    contest_path, contest_dir = _resolve_contest_input(str(contest_file), tmp_path)
    assert contest_path == contest_file
    assert contest_dir is None


def test_resolve_contest_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _resolve_contest_input("MISSING_CONTEST", tmp_path)
