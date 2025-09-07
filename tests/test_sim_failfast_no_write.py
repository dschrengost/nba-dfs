from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim


def test_failfast_invalid_field_blocks_writes(tmp_path: Path, monkeypatch):
    # Use stub to ensure we don't require a real impl (should not be reached)
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")

    # Invalid field: 7 players
    field_df = pd.DataFrame(
        [
            {
                "run_id": "RID",
                "entrant_id": 1,
                "origin": "variant",
                "players": [f"p{i}" for i in range(7)],
                "export_csv_row": "",
                "weight": 1.0,
            }
        ]
    )
    field_path = tmp_path / "bad_field.parquet"
    field_df.to_parquet(field_path)

    # Minimal contest fixture
    contest_path = Path(__file__).parent / "fixtures" / "contest_structure.csv"

    out_root = tmp_path / "out"
    rc = 0
    try:
        sim.run_adapter(
            slate_id="20251101_NBA",
            config_path=None,
            config_kv=None,
            seed=1,
            out_root=out_root,
            tag=None,
            field_path=field_path,
            from_field_run=None,
            variants_path=None,
            contest_path=contest_path,
            from_contest_dir=None,
        )
    except Exception:
        rc = 1
    assert rc == 1
    # No outputs written
    runs_dir = out_root / "runs" / "sim"
    assert not runs_dir.exists()
