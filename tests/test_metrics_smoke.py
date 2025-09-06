from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim
from processes.metrics import adapter as metrics


def _build_simple_field(tmp_path: Path) -> Path:
    players = [f"p{i}" for i in range(8)]
    dk_pos = [
        {"slot": s, "position": s}
        for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]
    df = pd.DataFrame(
        [
            {
                "run_id": "RID",
                "entrant_id": 1,
                "origin": "variant",
                "players": players,
                "export_csv_row": sim.export_csv_row_preview(players, dk_pos),
            },
            {
                "run_id": "RID",
                "entrant_id": 2,
                "origin": "variant",
                "players": players,  # deliberate duplicate to exercise dup_risk
                "export_csv_row": sim.export_csv_row_preview(players, dk_pos),
            },
        ]
    )
    path = tmp_path / "field.parquet"
    df.to_parquet(path)
    return path


def _contest_path() -> Path:
    return Path(__file__).parent / "fixtures" / "contest_structure.csv"


def test_metrics_from_sim_smoke(tmp_path: Path, monkeypatch):
    # Build a tiny sim run using stub simulator
    monkeypatch.setenv("GPP_SIM_IMPL", "tests.fixtures.stub_simulator:run_sim")
    field_path = _build_simple_field(tmp_path)
    out_root = tmp_path / "out"
    res = sim.run_adapter(
        slate_id="20251101_NBA",
        config_path=None,
        config_kv=None,
        seed=7,
        out_root=out_root,
        tag=None,
        field_path=field_path,
        from_field_run=None,
        variants_path=None,
        contest_path=_contest_path(),
        from_contest_dir=None,
    )

    sim_run_id = str(res["run_id"]) if "run_id" in res else ""
    assert sim_run_id

    # Run metrics adapter from the sim run
    mres = metrics.run_adapter(from_sim_run=sim_run_id, out_root=out_root, seed=123)
    mpath = Path(mres["metrics_path"]) if isinstance(mres["metrics_path"], str) else mres["metrics_path"]
    assert mpath.exists()

    df = pd.read_parquet(mpath)
    assert len(df) == 1
    aggs = df.iloc[0]["aggregates"]
    # Required keys present
    for k in ("roi_mean", "duplication_risk", "entropy"):
        assert k in aggs

    # Manifest and registry
    manifest = Path(mres["manifest_path"]) if isinstance(mres["manifest_path"], str) else mres["manifest_path"]
    registry = Path(mres["registry_path"]) if isinstance(mres["registry_path"], str) else mres["registry_path"]
    assert manifest.exists() and registry.exists()


