from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim


def test_smoke_adapter_end_to_end(tmp_path: Path, monkeypatch):
    # Use stub simulator via env var
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")

    # Field parquet (3 entrants)
    players = [f"p{i}" for i in range(8)]
    dk_pos = [{"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]]
    field_rows = []
    for i in range(1, 4):
        field_rows.append(
            {
                "run_id": "RID",
                "entrant_id": i,
                "origin": "variant",
                "variant_id": f"V{i}",
                "players": players,
                "export_csv_row": sim.export_csv_row_preview(players, dk_pos),
                "weight": 1.0,
                "total_salary": 49800,
            }
        )
    field_df = pd.DataFrame(field_rows)
    field_path = tmp_path / "field.parquet"
    field_df.to_parquet(field_path)

    contest_path = Path(__file__).parent / "fixtures" / "contest_structure.csv"

    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    result = sim.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=["num_trials=1"],
        seed=42,
        out_root=out_root,
        tag="PRP-5",
        field_path=field_path,
        from_field_run=None,
        variants_path=None,
        contest_path=contest_path,
        from_contest_dir=None,
    )

    run_id = result["run_id"]
    run_dir = out_root / "runs" / "sim" / run_id
    assert (run_dir / "artifacts" / "sim_results.parquet").exists()
    assert (run_dir / "artifacts" / "metrics.parquet").exists()
    assert (run_dir / "manifest.json").exists()

    # Registry appended
    registry = out_root / "registry" / "runs.parquet"
    assert registry.exists()
    reg_df = pd.read_parquet(registry)
    assert (reg_df["run_type"] == "sim").any()
