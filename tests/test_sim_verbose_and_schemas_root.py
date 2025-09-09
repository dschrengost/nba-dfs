from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim


def test_verbose_prints_inputs_and_runid(capsys, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")

    # Field parquet
    players = [f"p{i}" for i in range(8)]
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    field_df = pd.DataFrame(
        [
            {
                "run_id": "RID",
                "entrant_id": 1,
                "origin": "variant",
                "players": players,
                "export_csv_row": sim.export_csv_row_preview(players, dk_pos),
            }
        ]
    )
    field_path = tmp_path / "field.parquet"
    field_df.to_parquet(field_path)

    contest_path = Path(__file__).parent / "fixtures" / "contest_structure.csv"

    argv = [
        "--slate-id",
        "20251101_NBA",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--field",
        str(field_path),
        "--contest",
        str(contest_path),
        "--verbose",
    ]
    rc = sim.main(argv)
    assert rc == 0
    captured = capsys.readouterr()
    assert "[sim] field:" in captured.err
    assert str(field_path) in captured.err
    assert "[sim] contest:" in captured.err
    assert str(contest_path) in captured.err
    assert "[sim] run_id=" in captured.err
    assert "[sim] schemas_root:" in captured.err


def test_schemas_root_robust_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")

    # Field parquet
    players = [f"p{i}" for i in range(8)]
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    field_df = pd.DataFrame(
        [
            {
                "run_id": "RID",
                "entrant_id": 1,
                "origin": "variant",
                "players": players,
                "export_csv_row": sim.export_csv_row_preview(players, dk_pos),
            }
        ]
    )
    field_path = tmp_path / "field.parquet"
    field_df.to_parquet(field_path)
    contest_path = Path(__file__).parent / "fixtures" / "contest_structure.csv"

    argv = [
        "--slate-id",
        "20251101_NBA",
        "--seed",
        "1",
        "--out-root",
        str(tmp_path / "out"),
        "--field",
        str(field_path),
        "--contest",
        str(contest_path),
    ]
    rc = sim.main(argv)
    assert rc == 0
