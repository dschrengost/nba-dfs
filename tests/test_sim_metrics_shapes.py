from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim


def test_metrics_schema_and_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")

    players = [f"p{i}" for i in range(8)]
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    field = pd.DataFrame(
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
    field.to_parquet(field_path)
    contest_path = Path(__file__).parent / "fixtures" / "contest_structure.csv"

    out_root = tmp_path / "out"
    result = sim.run_adapter(
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
    metrics_path = (
        Path(result["metrics_path"])
        if isinstance(result["metrics_path"], str)
        else result["metrics_path"]
    )
    df = pd.read_parquet(metrics_path)
    agg = df.iloc[0]["aggregates"]
    assert set(["ev_mean", "roi_mean"]).issubset(set(agg.keys()))
