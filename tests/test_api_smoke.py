from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from processes.api import app as api_app

DK_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _make_players_csv(tmp: Path) -> tuple[Path, Path]:
    players_csv = tmp / "players.csv"
    proj_csv = tmp / "projections.csv"
    rows = [
        {"dk_player_id": f"P{i}", "name": f"Player {i}", "team": "BOS", "pos": "PG"}
        for i in range(1, 9)
    ]
    pd.DataFrame(rows).to_csv(players_csv, index=False)

    proj_rows = [
        {
            "DK_ID": f"P{i}",
            "Name": f"Player {i}",
            "Team": "BOS",
            "Pos": "PG",
            "Salary": 6000 + i * 100,
            "FP": 30.0 + i,
        }
        for i in range(1, 9)
    ]
    pd.DataFrame(proj_rows).to_csv(proj_csv, index=False)
    return players_csv, proj_csv


def _stub_optimizer_impl(
    projections_df: pd.DataFrame,
    constraints: Mapping[str, Any],
    seed: int,
    site: str,
    engine: str,
):
    col = "dk_player_id" if "dk_player_id" in projections_df.columns else "player_id"
    ids = list(map(str, projections_df[col].astype(str).head(8)))

    def _lineup():
        return {
            "players": ids,
            "dk_positions_filled": [{"slot": s, "position": s} for s in DK_SLOTS],
            "total_salary": 50000,
            "proj_fp": 250.0,
        }

    return [_lineup(), _lineup()], {"seed": seed, "engine": engine}


def _stub_variants_impl(
    parent_lineups_df: pd.DataFrame, knobs: Mapping[str, Any], seed: int
):
    variants: list[Mapping[str, Any]] = []
    for _, row in parent_lineups_df.head(1).iterrows():
        variants.append(
            {
                "variant_id": "V1",
                "parent_lineup_id": str(row["lineup_id"]),
                "players": list(row["players"]),
            }
        )
    return variants, {"seed": seed}


def _stub_field_impl(catalog_df: pd.DataFrame, knobs: Mapping[str, Any], seed: int):
    entrants = []
    v = catalog_df.iloc[0]
    entrants.append(
        {
            "origin": "variant",
            "variant_id": str(v["variant_id"]),
            "players": list(v["players"]),
            "weight": 1.0,
        }
    )
    return entrants, {"seed": seed}


def _stub_sim_impl(
    field_df: pd.DataFrame,
    contest: Mapping[str, Any],
    knobs: Mapping[str, Any],
    seed: int,
):
    rows = [
        {
            "world_id": 1,
            "entrant_id": int(field_df.iloc[0]["entrant_id"]),
            "score": 300.0,
            "rank": 1,
            "prize": 500.0,
        },
        {
            "world_id": 1,
            "entrant_id": 999999,
            "score": 100.0,
            "rank": contest.get("field_size", 2),
            "prize": 0.0,
        },
    ]
    aggs = {"ev_mean": 10.0, "roi_mean": 0.1}
    return rows, aggs, {"seed": seed}


@pytest.mark.anyio
async def test_api_run_orchestrator(tmp_path, monkeypatch):
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    players_csv, proj_csv = _make_players_csv(tmp_path)

    cfg = {
        "slate_id": "20250101_NBA",
        "seeds": {"optimizer": 1, "variants": 2, "field": 3, "sim": 4},
        "ingest": {
            "source": "manual",
            "projections": str(proj_csv),
            "player_ids": str(players_csv),
            "mapping": str(
                Path("pipeline/ingest/mappings/example_source.yaml").resolve()
            ),
        },
        "optimizer": {"site": "DK", "engine": "cbc", "config": {"num_lineups": 2}},
        "variants": {"config": {"num_variants": 1}},
        "field": {"config": {"field_size": 2}},
        "sim": {
            "config": {"num_trials": 5},
            "contest": {
                "field_size": 2,
                "payout_curve": [
                    {"rank_start": 1, "rank_end": 1, "prize": 500},
                    {"rank_start": 2, "rank_end": 2, "prize": 0},
                ],
                "entry_fee": 20,
                "rake": 0.15,
                "site": "DK",
            },
        },
    }

    import processes.field_sampler.adapter as fld
    import processes.gpp_sim.adapter as gsim
    import processes.optimizer.adapter as opt
    import processes.variants.adapter as var

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_optimizer_impl)
    monkeypatch.setattr(var, "_load_variant", lambda: _stub_variants_impl)
    monkeypatch.setattr(fld, "_load_sampler", lambda: _stub_field_impl)
    monkeypatch.setattr(gsim, "_load_sim_impl", lambda: _stub_sim_impl)

    payload = {
        "slate_id": "20250101_NBA",
        "config": cfg,
        "out_root": str(out_root),
        "schemas_root": str(Path("pipeline/schemas")),
    }

    async with AsyncClient(app=api_app, base_url="http://test") as ac:
        resp = await ac.post("/run/orchestrator", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        bundle_id = data["bundle_id"]
        sim_run_id = data["stages"]["sim"]

        resp2 = await ac.get(f"/runs/{bundle_id}")
        assert resp2.status_code == 200
        bundle = resp2.json()
        assert bundle["bundle_id"] == bundle_id

        resp3 = await ac.get(f"/metrics/{sim_run_id}")
        assert resp3.status_code == 200
        metrics = resp3.json()
        assert isinstance(metrics, list) and metrics
