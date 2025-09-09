from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from processes.field_sampler import adapter as field


def _export_row(players: list[str]) -> str:
    slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    return ",".join(f"{s} {p}" for s, p in zip(slots, players, strict=False))


def _stub_sampler(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    entrants = []
    for _, row in catalog_df.iterrows():
        players = list(row["players"])
        entrants.append(
            {"origin": "variant", "players": players, "export_csv_row": _export_row(players)}
        )
    return entrants


def test_manifest_registry_and_runid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vc = pd.DataFrame([{"players": [f"p{i}" for i in range(8)]}])
    cat = tmp_path / "vc.parquet"
    vc.to_parquet(cat)
    monkeypatch.setattr(field, "_load_sampler", lambda: _stub_sampler)

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return datetime(2025, 11, 1, 0, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(field, "datetime", FakeDT)
    out = tmp_path / "out"
    res1 = field.run_adapter(
        slate_id="S",
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out,
        tag=None,
        input_path=cat,
    )
    res2 = field.run_adapter(
        slate_id="S",
        config_path=None,
        config_kv=None,
        seed=1,
        out_root=out,
        tag=None,
        input_path=cat,
    )
    assert res1["run_id"] == res2["run_id"]
    reg = pd.read_parquet(Path(res1["registry_path"]))
    assert (reg["run_id"] == res1["run_id"]).any()
    run_dir = Path(res1["field_path"]).parent
    assert (run_dir / "field.parquet").exists()
    assert (run_dir / "metrics.parquet").exists()


def _bad_sampler(catalog_df: pd.DataFrame, knobs: dict[str, Any], seed: int):
    players = [f"p{i}" for i in range(7)]
    return [{"origin": "variant", "players": players, "export_csv_row": "PG p0"}]


def test_failfast_no_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vc = pd.DataFrame([{"players": [f"p{i}" for i in range(8)]}])
    cat = tmp_path / "vc.parquet"
    vc.to_parquet(cat)
    monkeypatch.setattr(field, "_load_sampler", lambda: _bad_sampler)
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        field.run_adapter(
            slate_id="S",
            config_path=None,
            config_kv=None,
            seed=1,
            out_root=out,
            tag=None,
            input_path=cat,
        )
    assert not (out / "runs" / "field").exists()
