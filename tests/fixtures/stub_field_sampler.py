from __future__ import annotations

from typing import Any


def run_sampler(catalog_df, config: dict[str, Any], seed: int) -> tuple[Any, dict[str, Any]]:
    """Stub sampler honoring diversity knob.

    - diversity < 0.5  => many duplicates (high duplication_risk)
    - diversity >= 0.5 => spread across unique lineups (lower duplication_risk)
    Returns (entrants_df_like, telemetry). Entrants may be a DataFrame; the adapter
    will coerce it to records.
    """
    import pandas as pd

    K = min(10, len(catalog_df)) if len(catalog_df) else 1
    base = (
        catalog_df.iloc[:K].copy()
        if len(catalog_df)
        else pd.DataFrame(
            [
                {
                    "players": [f"p{i}" for i in range(8)],
                    "export_csv_row": ",".join(
                        [
                            "PG p0",
                            "SG p1",
                            "SF p2",
                            "PF p3",
                            "C p4",
                            "G p5",
                            "F p6",
                            "UTIL p7",
                        ]
                    ),
                }
            ]
        )
    )

    diversity = float(config.get("diversity", 0.0) or 0.0)
    field_size = int(config.get("field_size", 20))

    rows: list[dict[str, Any]] = []
    if diversity < 0.5:
        # low diversity: repeat first lineup
        first = base.iloc[0]
        p = list(first.get("players", [f"p{i}" for i in range(8)]))
        exp = first.get(
            "export_csv_row",
            ",".join(
                [
                    f"PG {p[0]}",
                    f"SG {p[1]}",
                    f"SF {p[2]}",
                    f"PF {p[3]}",
                    f"C {p[4]}",
                    f"G {p[5]}",
                    f"F {p[6]}",
                    f"UTIL {p[7]}",
                ]
            ),
        )
        for i in range(field_size):
            rows.append(
                {
                    "origin": "stub",
                    "players": p,
                    "export_csv_row": exp,
                    "variant_id": first.get("variant_id", None),
                    "lineup_id": f"dup_{i}",
                    "weight": 1.0,
                }
            )
    else:
        # high diversity: cycle unique lineups and perturb a player to ensure distinct sets
        for i in range(field_size):
            r = base.iloc[i % len(base)]
            p = list(r.get("players", [f"p{j}" for j in range(8)]))
            p[-1] = f"x{i}"  # ensure distinct set
            exp = r.get(
                "export_csv_row",
                ",".join(
                    [
                        f"PG {p[0]}",
                        f"SG {p[1]}",
                        f"SF {p[2]}",
                        f"PF {p[3]}",
                        f"C {p[4]}",
                        f"G {p[5]}",
                        f"F {p[6]}",
                        f"UTIL {p[7]}",
                    ]
                ),
            )
            rows.append(
                {
                    "origin": "stub",
                    "players": p,
                    "export_csv_row": exp,
                    "variant_id": r.get("variant_id", None),
                    "lineup_id": f"u_{i}",
                    "weight": 1.0,
                }
            )

    entrants = pd.DataFrame(rows)
    telemetry = {"note": "stub_field_sampler honors diversity knob"}
    return entrants, telemetry
