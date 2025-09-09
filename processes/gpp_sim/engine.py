from __future__ import annotations

from typing import Any

import pandas as pd


def _normalize_players(player_ids: str) -> str:
    players = [p.strip() for p in player_ids.split("|") if p.strip()]
    return "|".join(sorted(players))


def run_sim(
    lineups: pd.DataFrame, contest: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run a minimal deterministic contest simulation.

    Parameters
    ----------
    lineups: DataFrame
        Columns: lineup_id, player_ids, entry_count, proj_points.
    contest: DataFrame
        Columns: place, payout with optional buy_in and rake (taken from first row).
    """
    df = lineups.copy()
    if "entry_count" not in df.columns:
        df["entry_count"] = 1
    df["player_set"] = df["player_ids"].map(_normalize_players)
    grouped = (
        df.groupby("player_set")
        .agg({"lineup_id": "first", "proj_points": "first", "entry_count": "sum"})
        .rename(columns={"proj_points": "score", "entry_count": "dup_count"})
        .reset_index()
    )

    # Expand for ranking
    expanded_rows: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        for _ in range(int(row["dup_count"])):
            expanded_rows.append(
                {
                    "player_set": row["player_set"],
                    "lineup_id": row["lineup_id"],
                    "score": float(row["score"]),
                }
            )
    entries_df = pd.DataFrame(expanded_rows)
    entries_df.sort_values("score", ascending=False, inplace=True, kind="mergesort")
    entries_df["finish"] = range(1, len(entries_df) + 1)

    # Payouts
    contest_sorted = contest.sort_values("place")
    payouts = contest_sorted["payout"].tolist()
    payouts.extend([0.0] * max(0, len(entries_df) - len(payouts)))

    entries_df["prize"] = 0.0
    for _score, group in entries_df.groupby("score", sort=False):
        idxs = group.index
        places = entries_df.loc[idxs, "finish"].astype(int).tolist()
        pay = [payouts[i - 1] for i in places]
        avg = sum(pay) / len(pay)
        entries_df.loc[idxs, "prize"] = avg

    agg = (
        entries_df.groupby("player_set")
        .agg(
            lineup_id=("lineup_id", "first"),
            score=("score", "first"),
            prize=("prize", "sum"),
            finish=("finish", "min"),
            dup_count=("lineup_id", "count"),
        )
        .reset_index(drop=True)
    )

    entries = int(entries_df.shape[0])
    buy_in = float(contest_sorted.get("buy_in", pd.Series([0.0])).iloc[0])
    total_prizes = float(agg["prize"].sum())
    total_fees = entries * buy_in
    net = total_prizes - total_fees
    roi = net / total_fees if total_fees else 0.0
    itm_entries = int((entries_df["prize"] > 0).sum())
    dup_counts = agg["dup_count"]
    summary: dict[str, Any] = {
        "entries": entries,
        "unique_lineups": int(agg.shape[0]),
        "total_prizes": round(total_prizes, 2),
        "total_fees": round(total_fees, 2),
        "net": round(net, 2),
        "roi": roi,
        "itm_pct": itm_entries / entries if entries else 0.0,
        "dup": {
            "mean": float(dup_counts.mean()) if not dup_counts.empty else 0.0,
            "p95": float(dup_counts.quantile(0.95)) if not dup_counts.empty else 0.0,
            "max": int(dup_counts.max()) if not dup_counts.empty else 0,
        },
    }

    return agg, summary
