from __future__ import annotations

from typing import Any

import pandas as pd


def run_sim(field_df: pd.DataFrame, contest: dict[str, Any], knobs: dict[str, Any], seed: int):
    # Deterministic: single world, entrants ranked by entrant_id ascending
    payout: dict[int, float] = {}
    for p in contest.get("payout_curve", []):
        for r in range(int(p.get("rank_start", 0)), int(p.get("rank_end", 0)) + 1):
            payout[r] = float(p.get("prize", 0.0))
    rows: list[dict[str, Any]] = []
    entrants = list(pd.to_numeric(field_df.get("entrant_id"), errors="coerce").fillna(0).astype(int))
    for i, eid in enumerate(sorted(entrants), start=1):
        rows.append(
            {
                "world_id": 0,
                "entrant_id": int(eid),
                "score": float(100 - i),
                "rank": int(i),
                "prize": float(payout.get(i, 0.0)),
                "seed": int(seed),
            }
        )
    aggregates = {"ev_mean": float(sum(payout.values()) / max(1, len(entrants))), "roi_mean": -0.1}
    telemetry = {"note": "stub"}
    return rows, aggregates, telemetry

