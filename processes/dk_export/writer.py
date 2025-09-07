from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _parse_export_row(export_row: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for token in str(export_row).split(","):
        token = token.strip()
        if not token:
            continue
        slot, _, pid = token.partition(" ")
        mapping[slot] = pid.strip()
    return mapping


def build_export_df(
    sim_results: pd.DataFrame,
    field_df: pd.DataFrame,
    top_n: int = 20,
    *,
    dedupe: bool = True,
) -> pd.DataFrame:
    """Select entrants and build DK export rows.

    Entrants are ranked by mean prize descending.
    """
    ev = sim_results.groupby("entrant_id")["prize"].mean().reset_index(name="ev")
    ev.sort_values("ev", ascending=False, inplace=True)
    entrant_ids: Sequence[Any] = ev.head(int(top_n))["entrant_id"].tolist()

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for eid in entrant_ids:
        subset = field_df[field_df["entrant_id"] == eid]
        if subset.empty:
            continue
        export_row = str(subset.iloc[0]["export_csv_row"])
        tokens = _parse_export_row(export_row)
        players = [tokens.get(slot, "") for slot in DK_SLOTS_ORDER]
        if "" in players:
            raise ValueError("Invalid export_csv_row: missing slots")
        key = tuple(players)
        if dedupe and key in seen:
            continue
        seen.add(key)
        row = {"entrant_id": eid}
        row.update(dict(zip(DK_SLOTS_ORDER, players, strict=True)))
        rows.append(row)
    return pd.DataFrame(rows)


def write_dk_csv(df: pd.DataFrame, out_csv: Path) -> None:
    df = df[["entrant_id", *DK_SLOTS_ORDER]]
    df.to_csv(out_csv, columns=DK_SLOTS_ORDER, index=False)


def fill_entries_template(
    entries_df: pd.DataFrame, export_df: pd.DataFrame
) -> pd.DataFrame:
    out = entries_df.copy()
    for i, (_, row) in enumerate(export_df.iterrows()):
        for slot in DK_SLOTS_ORDER:
            out.at[i, slot] = row[slot]
    return out


def update_entries_csv(
    entries_csv: Path,
    export_df: pd.DataFrame,
    out_path: Path | None = None,
) -> Path:
    df = pd.read_csv(entries_csv)
    filled = fill_entries_template(df, export_df)
    out = out_path or entries_csv
    filled.to_csv(out, index=False)
    return out


def discover_from_sim_run(
    run_id: str, runs_root: Path = Path("runs")
) -> tuple[Path, Path]:
    manifest_path = runs_root / "sim" / run_id / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    sim_path: Path | None = None
    field_path: Path | None = None
    for obj in data.get("outputs", []):
        if obj.get("kind") == "sim_results":
            sim_path = Path(obj["path"])
            break
    for obj in data.get("inputs", []):
        if obj.get("role") == "field":
            field_path = Path(obj["path"])
            break
    if sim_path is None or field_path is None:
        raise FileNotFoundError("Manifest missing sim_results or field paths")
    return sim_path, field_path
