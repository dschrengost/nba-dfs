from __future__ import annotations

import random
from typing import Any

import pandas as pd

from validators.lineup_rules import DK_SLOTS_ORDER


def run_sampler(
    catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Sample field entrants from a variant catalog.

    Parameters
    ----------
    catalog_df:
        DataFrame containing at minimum a ``players`` column of length-8 lists.
    knobs:
        Engine configuration produced by :func:`map_config_to_knobs`. Unknown
        keys are ignored.
    seed:
        RNG seed to ensure determinism.

    Returns
    -------
    entrants, telemetry
        ``entrants`` is a list of mappings with ``players`` and optional
        ``variant_id``/``lineup_id``. ``telemetry`` contains auxiliary metrics.
    """
    rng = random.Random(seed)
    field_size = int(knobs.get("field_size", 0) or len(catalog_df))
    idxs = list(range(len(catalog_df)))
    rng.shuffle(idxs)

    entrants: list[dict[str, Any]] = []
    for idx in idxs[:field_size]:
        row = catalog_df.iloc[idx]
        players = list(row.get("players") or [])
        export_row = row.get("export_csv_row")
        if not export_row:
            export_row = ",".join(f"{s} {p}" for s, p in zip(DK_SLOTS_ORDER, players, strict=False))
        ent: dict[str, Any] = {
            "origin": "variant",
            "variant_id": str(row.get("variant_id", "")),
            "players": players,
            "export_csv_row": str(export_row),
            "weight": float(row.get("weight", 1.0)),
        }
        lineup_id = row.get("lineup_id")
        if lineup_id is not None and not pd.isna(lineup_id):
            ent["lineup_id"] = str(lineup_id)
        entrants.append(ent)

    telemetry = {"sampled": len(entrants)}
    return entrants, telemetry
