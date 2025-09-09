from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .engine import run_sim
from .io_schemas import load_contest, load_lineups


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Minimal GPP contest simulator")
    p.add_argument("--lineups", type=Path, required=True)
    p.add_argument("--contest", type=Path, required=True)
    p.add_argument("--outdir", type=Path, default=Path("runs"))
    p.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    ns = p.parse_args(argv)

    lineups = load_lineups(ns.lineups)
    contest = load_contest(ns.contest)
    results, summary = run_sim(lineups, contest)

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = ns.outdir / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    if ns.format == "csv":
        results.to_csv(run_dir / "sim_results.csv", index=False)
    else:
        results.to_parquet(run_dir / "sim_results.parquet", index=False)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
