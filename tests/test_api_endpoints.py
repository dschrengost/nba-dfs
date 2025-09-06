from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient

from processes.api import app as api_app


@pytest.mark.anyio
async def test_list_runs_registry(tmp_path: Path) -> None:
    # Build a small registry parquet
    reg_dir = tmp_path / "data" / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    reg_path = reg_dir / "runs.parquet"
    df = pd.DataFrame(
        [
            {
                "run_id": "20250101_120000_deadbeef",
                "run_type": "sim",
                "slate_id": "20250101_NBA",
                "status": "success",
                "primary_outputs": ["/path/to/sim_results.parquet"],
                "metrics_path": "/path/to/metrics.parquet",
                "created_ts": "2025-01-01T12:00:00.000Z",
                "tags": ["test"],
            }
        ]
    )
    df.to_parquet(reg_path)

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get("/runs", params={"registry_path": str(reg_path)})
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data and isinstance(data["runs"], list)
        assert data["runs"][0]["run_id"] == "20250101_120000_deadbeef"


@pytest.mark.anyio
async def test_export_dk_csv_from_sim_run(tmp_path: Path) -> None:
    # Create a sim run manifest and parquet artifacts
    runs_root = tmp_path / "runs"
    run_id = "RID123"
    run_dir = runs_root / "sim" / run_id
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Field with export_csv_row
    def _row(players: list[str]) -> str:
        slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        return ",".join(f"{s} {p}" for s, p in zip(slots, players, strict=True))

    field_rows = [
        {"entrant_id": 1, "export_csv_row": _row([f"p{i}" for i in range(1, 9)])},
        {"entrant_id": 2, "export_csv_row": _row([f"q{i}" for i in range(1, 9)])},
    ]
    field_df = pd.DataFrame(field_rows)
    field_path = artifacts / "field.parquet"
    field_df.to_parquet(field_path)

    # Sim results with two entrants and EV favoring entrant 1
    sim_rows = [
        {"world_id": 1, "entrant_id": 1, "prize": 100.0},
        {"world_id": 1, "entrant_id": 2, "prize": 10.0},
    ]
    sim_df = pd.DataFrame(sim_rows)
    sim_path = artifacts / "sim_results.parquet"
    sim_df.to_parquet(sim_path)

    manifest = {
        "schema_version": "0.2.0",
        "run_id": run_id,
        "run_type": "sim",
        "slate_id": "20250101_NBA",
        "created_ts": "2025-01-01T12:00:00.000Z",
        "inputs": [
            {
                "path": str(field_path),
                "content_sha256": "x" * 64,
                "role": "field",
            }
        ],
        "outputs": [
            {"path": str(sim_path), "kind": "sim_results"},
            {"path": str(field_path), "kind": "field"},
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get(
            f"/export/dk/{run_id}", params={"runs_root": str(runs_root), "top_n": 2}
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/csv")
        csv_text = resp.text.strip().splitlines()
        # header + 2 rows
        assert len(csv_text) == 1 + 2
        assert csv_text[0].startswith("PG,SG,SF,PF,C,G,F,UTIL")


@pytest.mark.anyio
async def test_logs_placeholder(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_id = "RIDLOG"
    run_dir = runs_root / "sim" / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    # minimal manifest
    manifest = {
        "schema_version": "0.2.0",
        "run_id": run_id,
        "run_type": "sim",
        "slate_id": "20250101_NBA",
        "created_ts": "2025-01-01T12:00:00.000Z",
        "inputs": [],
        "outputs": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # write a logs.txt
    (run_dir / "logs.txt").write_text("hello log", encoding="utf-8")

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get(f"/logs/{run_id}", params={"runs_root": str(runs_root)})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["run_id"] == run_id
        assert "hello log" in payload.get("logs", "")
