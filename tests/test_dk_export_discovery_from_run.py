from __future__ import annotations

import json
from pathlib import Path

from processes.dk_export.writer import discover_from_sim_run


def test_dk_export_discovery_from_run(tmp_path: Path) -> None:
    run_id = "RID"
    runs_root = tmp_path / "runs"
    manifest_dir = runs_root / "sim" / run_id
    manifest_dir.mkdir(parents=True)
    manifest = {
        "outputs": [{"path": "sim_results.parquet", "kind": "sim_results"}],
        "inputs": [{"path": "field.parquet", "role": "field"}],
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest))
    sim_path, field_path = discover_from_sim_run(run_id, runs_root)
    assert sim_path == Path("sim_results.parquet")
    assert field_path == Path("field.parquet")
