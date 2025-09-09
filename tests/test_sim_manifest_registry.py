from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from processes.gpp_sim import adapter as sim


def test_manifest_and_registry(tmp_path: Path, monkeypatch):
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
        tag="PRP-5",
        field_path=field_path,
        from_field_run=None,
        variants_path=None,
        contest_path=contest_path,
        from_contest_dir=None,
    )
    run_id = result["run_id"]
    manifest_path = out_root / "runs" / "sim" / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kinds = [o["kind"] for o in manifest.get("outputs", [])]
    assert "sim_results" in kinds and "sim_metrics" in kinds
    # Inputs include expected roles
    roles = set(i.get("role") for i in manifest.get("inputs", []))
    assert {"field", "contest_structure"}.issubset(roles)
    assert "schema_version" in manifest

    registry = out_root / "registry" / "runs.parquet"
    df = pd.read_parquet(registry)
    assert (df["run_type"] == "sim").any()
    assert (df["run_id"] == run_id).any()
