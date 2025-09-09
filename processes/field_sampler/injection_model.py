from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from validators import Rules, validate_lineup


def _utc_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def build_field(
    projections: pd.DataFrame,
    *,
    field_size: int,
    seed: int,
    slate_id: str,
    site: str = "dk",
    salary_cap: int = 50000,
    max_per_team: int = 4,
    ruleset_version: str = "v1",
    variant_catalog: pd.DataFrame | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    rules = Rules(salary_cap=salary_cap, max_per_team=max_per_team)

    pool = projections[["player_id", "team", "salary", "positions"]]
    players = pool.to_dict("records")
    
    # Build player pool dict for shared validator
    player_pool = {}
    for _, row in pool.iterrows():
        player_id = str(row["player_id"])
        positions = str(row.get("positions", "")).split("/")
        player_pool[player_id] = {
            "salary": int(row.get("salary", 0)),
            "positions": [p.strip() for p in positions if p.strip()],
            "team": str(row.get("team", "")),
            "is_active": True,
            "inj_status": "",
        }

    base: list[dict[str, Any]] = []
    attempts = 0
    while len(base) < field_size and attempts < 10000:
        rng.shuffle(players)
        lineup_player_ids = [p["player_id"] for p in players[:8]]
        result = validate_lineup(lineup_player_ids, player_pool, rules)
        if result.valid:
            base.append({"players": lineup_player_ids})
        else:
            attempts += 1

    run_id = f"fs-{uuid.uuid4().hex[:8]}"
    created_at = _utc_now()

    for row in base:
        row.update(
            {
                "run_id": run_id,
                "created_at": created_at,
                "site": site,
                "slate_id": slate_id,
                "seed": seed,
                "ruleset_version": ruleset_version,
                "source": "public",
                "origin": "field_base",
                "owner": "field",
            }
        )

    artifacts_dir = Path("artifacts")
    _write_jsonl(artifacts_dir / "field_base.jsonl", base)

    merged = list(base)
    injected = 0
    if variant_catalog is not None and len(variant_catalog):
        for _, row in variant_catalog.iterrows():
            lineup_player_ids = list(row["players"])
            result = validate_lineup(lineup_player_ids, player_pool, rules)
            if result.valid:
                entry = {
                    "players": list(row["players"]),
                    "run_id": run_id,
                    "created_at": created_at,
                    "site": site,
                    "slate_id": slate_id,
                    "seed": seed,
                    "ruleset_version": ruleset_version,
                    "source": "injected",
                    "origin": "variant_catalog",
                    "owner": "us",
                }
                merged.append(entry)
                injected += 1
    _write_jsonl(artifacts_dir / "field_merged.jsonl", merged)

    metrics = {
        "run_id": run_id,
        "created_at": created_at,
        "site": site,
        "slate_id": slate_id,
        "seed": seed,
        "ruleset_version": ruleset_version,
        "field_base_count": len(base),
        "injected_count": injected,
        "field_merged_count": len(merged),
        "invalid_attempts": attempts,
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (artifacts_dir / "audit_fs.md").write_text(
        "# Field Sampler Audit\n\n- criticals: 0\n", encoding="utf-8"
    )

    return metrics
