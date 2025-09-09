from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from field_sampler.engine import run_sampler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.sample_field")
    p.add_argument("--projections", type=Path, required=True)
    p.add_argument("--slate", type=Path)
    p.add_argument("--contest-config", type=Path)
    p.add_argument("--field-size", type=int, required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-dir", type=Path, default=Path("artifacts"))
    p.add_argument("--site", default="dk")
    p.add_argument("--slate-id", required=True)
    args = p.parse_args(argv)

    projections = pd.read_csv(args.projections)
    if args.slate:
        _ = pd.read_csv(args.slate)
    contest = {}
    if args.contest_config:
        contest = json.loads(args.contest_config.read_text(encoding="utf-8"))
    config = {
        "salary_cap": contest.get("salary_cap", 50000),
        "max_per_team": contest.get("max_per_team", 4),
        "site": args.site,
        "slate_id": args.slate_id,
        "field_size": args.field_size,
        "out_dir": args.out_dir,
    }
    run_sampler(
        projections=projections,
        config=config,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
