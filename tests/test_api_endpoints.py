from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient

from processes.api import app as api_app


@pytest.mark.anyio
async def test_runs_registry_missing_404(tmp_path: Path) -> None:
    missing = tmp_path / "data" / "registry" / "runs.parquet"
    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get("/runs", params={"registry_path": str(missing)})
        assert resp.status_code == 404
        payload = resp.json()
        assert payload["error"] == "not_found"
        assert "registry" in payload.get("detail", "")


@pytest.mark.anyio
async def test_export_dk_csv_variants_bad_export_row_422(tmp_path: Path) -> None:
    # Create a variants run with a catalog missing export_csv_row
    runs_root = tmp_path / "runs"
    run_id = "VAR_BAD"
    run_dir = runs_root / "variants" / run_id
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # minimal catalog without export_csv_row column
    cat_df = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "variant_id": "V1",
                "parent_lineup_id": "L1",
                "players": [f"p{i}" for i in range(8)],
                "variant_params": {"_": None},
            }
        ]
    )
    catalog_path = artifacts / "variant_catalog.parquet"
    cat_df.to_parquet(catalog_path)

    manifest = {
        "schema_version": "0.2.0",
        "run_id": run_id,
        "run_type": "variants",
        "slate_id": "20250101_NBA",
        "created_ts": "2025-01-01T12:00:00.000Z",
        "inputs": [],
        "outputs": [
            {"path": str(catalog_path), "kind": "variant_catalog"},
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get(f"/export/dk/{run_id}", params={"runs_root": str(runs_root)})
        assert resp.status_code == 422
        payload = resp.json()
        assert payload["error"] == "invalid_export"
        assert "export_csv_row" in payload.get("detail", "")


@pytest.mark.anyio
async def test_logs_fallback_message_no_logs(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_id = "RID_NO_LOG"
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

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.get(f"/logs/{run_id}", params={"runs_root": str(runs_root)})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["run_id"] == run_id
        assert payload.get("message") == "logs not available"
