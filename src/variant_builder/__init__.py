from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.runs.api import _git_branch, gen_run_id
from validators.lineup_rules import DK_SLOTS_ORDER, LineupValidator

__all__ = ["BuildParams", "build_variant_catalog"]


@dataclass
class BuildParams:
    """Parameters for variant catalog construction."""

    optimizer_run: Path
    player_pool: Path
    output_path: Path
    slate_id: str
    site: str = "DK"
    run_id: str | None = None


def _utc_now_iso() -> str:
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


def _load_optimizer_run(path: Path) -> Iterable[list[tuple[str, str]]]:
    """Yield lineups from optimizer run JSONL.

    Each line is expected to be a JSON object containing either:
    - "slots": list of {"slot": str, "player_id": str}
    - "lineup": list of [slot, player_id]
    - "players": list of player_ids ordered according to DK slots
    """
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "slots" in obj:
                yield [(s["slot"], s["player_id"]) for s in obj["slots"]]
            elif "lineup" in obj:
                yield [tuple(pair) for pair in obj["lineup"]]
            elif "players" in obj:
                players = list(obj["players"])
                yield list(zip(DK_SLOTS_ORDER, players, strict=True))
            else:  # pragma: no cover - defensive
                raise ValueError("optimizer run row missing lineup data")


def build_variant_catalog(params: BuildParams) -> Path:
    """Build a variant catalog from an optimizer run.

    Validates each lineup using :class:`LineupValidator` and writes a JSONL file
    containing the minimal contract required for downstream injection.
    """
    run_id = params.run_id or gen_run_id()
    created_at = _utc_now_iso()
    source_branch = _git_branch()

    pool = pd.read_csv(params.player_pool).set_index("player_id")
    pool_df = pool.reset_index()

    validator = LineupValidator()

    params.output_path.parent.mkdir(parents=True, exist_ok=True)
    with params.output_path.open("w", encoding="utf-8") as out:
        for lineup in _load_optimizer_run(params.optimizer_run):
            if not validator.validate(lineup, pool_df):
                raise ValueError("Invalid lineup in optimizer run")
            player_ids = [pid for _, pid in lineup]
            sub = pool.loc[player_ids]
            record = {
                "lineup": player_ids,
                "salary_total": int(sub["salary"].sum()),
                "teams": list(sub["team"].unique()),
                "valid": True,
                "tags": [],
                "run_id": run_id,
                "created_at": created_at,
                "site": params.site,
                "slate_id": params.slate_id,
                "source_branch": source_branch,
            }
            out.write(json.dumps(record) + "\n")
    return params.output_path


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - thin CLI
    import argparse

    p = argparse.ArgumentParser(prog="python -m src.variant_builder")
    p.add_argument("--optimizer-run", type=Path, required=True)
    p.add_argument("--player-pool", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--slate-id", required=True)
    p.add_argument("--site", default="DK")
    p.add_argument("--run-id")
    args = p.parse_args(argv)

    build_variant_catalog(
        BuildParams(
            optimizer_run=args.optimizer_run,
            player_pool=args.player_pool,
            output_path=args.out,
            slate_id=args.slate_id,
            site=args.site,
            run_id=args.run_id,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
