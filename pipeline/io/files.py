from __future__ import annotations

from pathlib import Path

import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Rely on pyarrow/fastparquet via pandas
    df.to_parquet(path)  # type: ignore[call-arg]

