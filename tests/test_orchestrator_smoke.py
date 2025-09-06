from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from processes.orchestrator import adapter as orch

DK_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _make_players_csv(tmp: Path) -> tuple[Path, Path]:
    players_csv = tmp / "players.csv"
    proj_csv = tmp / "projections.csv"
    # 8 simple players
    rows = [
        {"dk_player_id": f"P{i}", "name": f"Player {i}", "team": "BOS", "pos": "PG"}
        for i in range(1, 9)
    ]
    pd.DataFrame(rows).to_csv(players_csv, index=False)

    # projections use mapping headers (raw headers): DK_ID, Name, Team, Pos, Salary, FP
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
    # Build 2 trivial lineups from first 8 player ids
    col = "dk_player_id" if "dk_player_id" in projections_df.columns else "player_id"
    ids = list(map(str, projections_df[col].astype(str).head(8)))

    def _lineup():
        return {
            "players": ids,
            "dk_positions_filled": [{"slot": s, "position": s} for s in DK_SLOTS],
            "total_salary": 50000,
            "proj_fp": 250.0,
        }

    return [
        _lineup(),
        _lineup(),
    ], {"seed": seed, "engine": engine}


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
                # proj_fp/total_salary optional; adapter computes deltas
            }
        )
    return variants, {"seed": seed}


def _stub_field_impl(catalog_df: pd.DataFrame, knobs: Mapping[str, Any], seed: int):
    entrants = []
    # Take first variant
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


def test_orchestrator_smoke(tmp_path, monkeypatch):
    # Prepare inputs
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    players_csv, proj_csv = _make_players_csv(tmp_path)

    # Write orchestrator config
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
    cfg_path = tmp_path / "orch.yaml"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    # Monkeypatch stage implementations
    import processes.field_sampler.adapter as fld
    import processes.gpp_sim.adapter as gsim
    import processes.optimizer.adapter as opt
    import processes.variants.adapter as var

    monkeypatch.setattr(opt, "_load_optimizer", lambda: _stub_optimizer_impl)
    monkeypatch.setattr(var, "_load_variant", lambda: _stub_variants_impl)
    monkeypatch.setattr(fld, "_load_sampler", lambda: _stub_field_impl)
    monkeypatch.setattr(gsim, "_load_sim_impl", lambda: _stub_sim_impl)

    # Execute orchestrator
    res = orch.run_bundle(
        slate_id="20250101_NBA",
        config_path=cfg_path,
        config_kv=None,
        out_root=out_root,
        schemas_root=Path("pipeline/schemas"),
        validate=True,
        dry_run=False,
        verbose=True,
    )

    bundle_path = Path(res["bundle_path"])  # type: ignore[index]
    assert bundle_path.exists(), "bundle.json should be created"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle.get("bundle_id")
    assert [s["name"] for s in bundle.get("stages", [])] == [
        "ingest",
        "optimizer",
        "variants",
        "field",
        "sim",
    ]

    # Validate that each stage manifest exists
    for s in bundle["stages"]:
        mpath = Path(s["manifest"]).resolve()
        assert mpath.exists(), f"manifest should exist for stage {s['name']}"
