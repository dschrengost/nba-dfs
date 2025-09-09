from __future__ import annotations

from processes.optimizer.adapter import export_csv_row


def test_export_csv_row_header_order():
    players = [f"p{i}" for i in range(8)]
    dk_positions_filled = [
        {"slot": s, "position": s} for s in ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    ]

    row = export_csv_row(players, dk_positions_filled)
    # Expect tokens in header order
    parts = row.split(",")
    assert len(parts) == 8
    assert parts[0].startswith("PG ") and parts[0].endswith("p0")
    assert parts[1].startswith("SG ") and parts[1].endswith("p1")
    assert parts[2].startswith("SF ") and parts[2].endswith("p2")
    assert parts[3].startswith("PF ") and parts[3].endswith("p3")
    assert parts[4].startswith("C ") and parts[4].endswith("p4")
    assert parts[5].startswith("G ") and parts[5].endswith("p5")
    assert parts[6].startswith("F ") and parts[6].endswith("p6")
    assert parts[7].startswith("UTIL ") and parts[7].endswith("p7")
