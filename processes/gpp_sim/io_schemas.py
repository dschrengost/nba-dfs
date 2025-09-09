from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel


class LineupRow(BaseModel):  # type: ignore[misc]
    lineup_id: str
    player_ids: str
    entry_count: int | None = 1
    proj_points: float


class ContestRow(BaseModel):  # type: ignore[misc]
    place: int
    payout: float
    buy_in: float | None = None
    rake: float | None = None


def load_lineups(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    out_rows: list[dict[str, Any]] = []
    for rec in df.to_dict(orient="records"):
        row = LineupRow(**rec)
        out_rows.append(row.model_dump())
    return pd.DataFrame(out_rows)


def load_contest(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".json":
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        payouts = data.get("payout_table") or data.get("payouts")
        if payouts is None:
            raise ValueError("contest JSON missing payout_table")
        rows = [
            {
                "place": i + 1,
                "payout": float(p),
                "buy_in": data.get("buy_in"),
                "rake": data.get("rake"),
            }
            for i, p in enumerate(payouts)
        ]
        return pd.DataFrame(rows)
    df = pd.read_csv(path)
    out_rows: list[dict[str, Any]] = []
    for rec in df.to_dict(orient="records"):
        row = ContestRow(**rec)
        out_rows.append(row.model_dump())
    return pd.DataFrame(out_rows)
