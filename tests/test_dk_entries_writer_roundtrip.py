from __future__ import annotations

from pathlib import Path

import pandas as pd

from processes.dk_export.writer import (
    DK_SLOTS_ORDER,
    build_export_df,
    update_entries_csv,
)


def _export_row(players: list[str]) -> str:
    return ",".join(f"{slot} {pid}" for slot, pid in zip(DK_SLOTS_ORDER, players, strict=True))


def test_dk_entries_writer_roundtrip(tmp_path: Path) -> None:
    players1 = [f"p{i}" for i in range(8)]
    players2 = [f"q{i}" for i in range(8)]
    field_df = pd.DataFrame(
        [
            {"entrant_id": 1, "export_csv_row": _export_row(players1)},
            {"entrant_id": 2, "export_csv_row": _export_row(players2)},
        ]
    )
    sim_df = pd.DataFrame(
        [
            {"entrant_id": 1, "prize": 10.0},
            {"entrant_id": 2, "prize": 9.0},
        ]
    )
    export_df = build_export_df(sim_df, field_df, top_n=2)
    template = Path(__file__).parent / "fixtures" / "dk_entries_template.csv"
    out = tmp_path / "filled.csv"
    update_entries_csv(template, export_df, out)
    result = pd.read_csv(out)
    for i, slot in enumerate(DK_SLOTS_ORDER):
        assert result.loc[0, slot] == players1[i]
        assert result.loc[1, slot] == players2[i]
