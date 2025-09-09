from __future__ import annotations

import pandas as pd

from processes.dk_export.writer import DK_SLOTS_ORDER, build_export_df


def _export_row(players: list[str]) -> str:
    return ",".join(f"{slot} {pid}" for slot, pid in zip(DK_SLOTS_ORDER, players, strict=True))


def test_dk_export_from_sim_topn() -> None:
    entrants = []
    field_rows = []
    for eid in range(1, 11):
        players = [f"p{eid}{i}" for i in range(8)]
        field_rows.append({"entrant_id": eid, "export_csv_row": _export_row(players)})
        entrants.append({"entrant_id": eid, "prize": 100 - eid})
    sim_df = pd.DataFrame(entrants)
    field_df = pd.DataFrame(field_rows)
    df = build_export_df(sim_df, field_df, top_n=5)
    assert len(df) == 5
    # Expect entrants with highest prize values (1..5)
    assert df["entrant_id"].tolist() == list(range(1, 6))
