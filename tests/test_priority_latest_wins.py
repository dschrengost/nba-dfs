from __future__ import annotations

import pandas as pd

from pipeline.ingest.cli import MappingSpec, apply_latest_wins_priority, normalize_projections


def test_latest_wins_tiebreaker() -> None:
    # two rows for same player with different updated_ts and source
    data = pd.DataFrame(
        {
            "DK_ID": ["1001", "1001"],
            "Name": ["Player A", "Player A"],
            "Team": ["BOS", "BOS"],
            "Pos": ["SF/PF", "SF/PF"],
            "Salary": [9800, 9900],
            "Minutes": [36, 35],
            "FP": [48.2, 47.0],
        }
    )
    mapping = MappingSpec(name="ex", header_map={"DK_ID": "dk_player_id", "Name": "name", "Team": "team", "Pos": "pos", "Salary": "salary", "Minutes": "minutes", "FP": "proj_fp"}, source_fields=["DK_ID", "Name", "Team", "Pos", "Salary", "Minutes", "FP"])

    df1 = normalize_projections(data.iloc[[0]], mapping, "20251101_NBA", "other", updated_ts="2025-11-01T16:00:00.000Z", content_sha256="a" * 64)
    df2 = normalize_projections(data.iloc[[1]], mapping, "20251101_NBA", "manual", updated_ts="2025-11-01T15:59:00.000Z", content_sha256="b" * 64)
    combined = pd.concat([df1, df2], ignore_index=True)

    # Although manual has earlier timestamp, precedence should beat others on tie-break when timestamps equal; but here latest timestamp wins.
    deduped = apply_latest_wins_priority(combined)
    assert len(deduped) == 1
    # latest by updated_ts wins: df1 (other, 16:00) vs df2 (manual, 15:59)
    assert deduped.iloc[0]["salary"] == 9800

    # Now force same timestamp to test precedence
    df1_same = df1.copy()
    df1_same.loc[:, "updated_ts"] = "2025-11-01T16:00:00.000Z"
    df2_same = df2.copy()
    df2_same.loc[:, "updated_ts"] = "2025-11-01T16:00:00.000Z"
    deduped2 = apply_latest_wins_priority(pd.concat([df1_same, df2_same], ignore_index=True))
    assert len(deduped2) == 1
    # manual should beat other on tie
    assert deduped2.iloc[0]["source"] == "manual"

