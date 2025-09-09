from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .writer import (
    build_export_df,
    discover_from_sim_run,
    fill_entries_template,
    write_dk_csv,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.dk_export")
    p.add_argument("--from-sim-run")
    p.add_argument("--sim-results", type=Path)
    p.add_argument("--field", type=Path)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--out-csv", type=Path, required=True)
    p.add_argument("--no-dedupe", action="store_true")
    p.add_argument("--entries-csv", type=Path)
    p.add_argument("--entries-out", type=Path)
    p.add_argument("--runs-root", type=Path, default=Path("runs"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.from_sim_run:
        sim_path, field_path = discover_from_sim_run(args.from_sim_run, args.runs_root)
    else:
        sim_path = args.sim_results
        field_path = args.field
    sim_df = pd.read_parquet(sim_path)
    field_df = pd.read_parquet(field_path)
    export_df = build_export_df(sim_df, field_df, top_n=args.top_n, dedupe=not args.no_dedupe)
    write_dk_csv(export_df, args.out_csv)
    if args.entries_csv:
        entries_df = pd.read_csv(args.entries_csv)
        filled = fill_entries_template(entries_df, export_df)
        out = args.entries_out or args.entries_csv
        filled.to_csv(out, index=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
