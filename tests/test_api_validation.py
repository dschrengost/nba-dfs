from __future__ import annotations

import pytest
from httpx import AsyncClient

from processes.api import app as api_app


@pytest.mark.anyio
async def test_run_orchestrator_validation_missing_slate_id():
    payload = {
        # 'slate_id' missing
        "config": {
            "ingest": {},
            "optimizer": {},
            "variants": {},
            "field": {},
            "sim": {},
        }
    }
    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.post("/run/orchestrator", json=payload)
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_run_orchestrator_validation_config_wrong_type():
    payload = {
        "slate_id": "20250101_NBA",
        # config must be an object, not a string
        "config": "not-a-dict",
    }
    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.post("/run/orchestrator", json=payload)
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_run_orchestrator_validation_optimizer_site_literal():
    payload = {
        "slate_id": "20250101_NBA",
        "config": {
            "ingest": {},
            "optimizer": {"site": "FD"},  # invalid: Literal['DK']
            "variants": {},
            "field": {},
            "sim": {},
        },
    }
    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.post("/run/orchestrator", json=payload)
        assert resp.status_code == 422
