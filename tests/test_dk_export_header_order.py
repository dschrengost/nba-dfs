from __future__ import annotations

import pandas as pd

from processes.dk_export.writer import DK_SLOTS_ORDER, build_export_df


def _export_row(players: list[str]) -> str:
    return ",".join(
        f"{slot} {pid}" for slot, pid in zip(DK_SLOTS_ORDER, players, strict=True)
    )


def test_dk_export_header_order() -> None:
    players = [f"p{i}" for i in range(8)]
    field_df = pd.DataFrame(
        [
            {
                "entrant_id": 1,
                "export_csv_row": _export_row(players),
            }
        ]
    )
    sim_df = pd.DataFrame([{"entrant_id": 1, "prize": 10.0}])
    df = build_export_df(sim_df, field_df, top_n=1)
    assert list(df.columns) == ["entrant_id", *DK_SLOTS_ORDER]
    assert df.loc[0, "PG"] == "p0"
    assert df.loc[0, "UTIL"] == "p7"
