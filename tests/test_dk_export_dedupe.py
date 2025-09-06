from __future__ import annotations

import pandas as pd

from processes.dk_export.writer import DK_SLOTS_ORDER, build_export_df


def _export_row(players: list[str]) -> str:
    return ",".join(
        f"{slot} {pid}" for slot, pid in zip(DK_SLOTS_ORDER, players, strict=True)
    )


def test_dk_export_dedupe() -> None:
    players = [f"p{i}" for i in range(8)]
    field_df = pd.DataFrame(
        [
            {"entrant_id": 1, "export_csv_row": _export_row(players)},
            {"entrant_id": 2, "export_csv_row": _export_row(players)},
        ]
    )
    sim_df = pd.DataFrame(
        [
            {"entrant_id": 1, "prize": 50.0},
            {"entrant_id": 2, "prize": 40.0},
        ]
    )
    df = build_export_df(sim_df, field_df, top_n=2, dedupe=True)
    assert len(df) == 1
    df_no = build_export_df(sim_df, field_df, top_n=2, dedupe=False)
    assert len(df_no) == 2
