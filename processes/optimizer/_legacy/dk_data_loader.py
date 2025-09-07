from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass
class DKDataConfig:
    pass


def load_dk_strict_projections(projections_path: str, player_ids_path: str | None = None) -> pd.DataFrame:
    # Minimal stub: allow reading CSV and return as-is
    return pd.read_csv(projections_path)


def validate_dk_strict_data(df: pd.DataFrame) -> dict[str, Any]:
    return {"ok": True}

