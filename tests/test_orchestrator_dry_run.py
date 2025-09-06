from __future__ import annotations

from pathlib import Path

from processes.orchestrator import adapter as orch


def test_orchestrator_dry_run(tmp_path):
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "orch.json"
    cfg_path.write_text("{}", encoding="utf-8")

    res = orch.run_bundle(
        slate_id="20250101_NBA",
        config_path=cfg_path,
        config_kv=["ingest.source=manual"],
        out_root=out_root,
        schemas_root=Path("pipeline/schemas"),
        validate=True,
        dry_run=True,
        verbose=True,
    )
    assert res["bundle_id"] == "DRY_RUN"
    assert any("ingest:" in step for step in res["plan"])  # type: ignore[index]
