#!/usr/bin/env python3
"""CLI interface for the orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import run_orchestrated_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the orchestrator CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m processes.orchestrator",
        description="Execute end-to-end orchestrated pipeline: variants → optimizer → field_sampler → gpp_sim",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Execute the complete orchestrated pipeline",
    )

    run_parser.add_argument(
        "--slate",
        required=True,
        help="Slate ID (e.g., 2025-10-25)",
    )

    run_parser.add_argument(
        "--contest",
        required=True,
        help="Contest identifier (e.g., DK_MME_20)",
    )

    run_parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Global seed for deterministic execution",
    )

    run_parser.add_argument(
        "--variants-config",
        type=Path,
        required=True,
        help="Path to variants configuration YAML file",
    )

    run_parser.add_argument(
        "--optimizer-config",
        type=Path,
        required=True,
        help="Path to optimizer configuration YAML file",
    )

    run_parser.add_argument(
        "--sampler-config",
        type=Path,
        required=True,
        help="Path to field sampler configuration YAML file",
    )

    run_parser.add_argument(
        "--sim-config",
        type=Path,
        required=True,
        help="Path to simulation configuration YAML file",
    )

    run_parser.add_argument(
        "--tag",
        help="Optional tag for this run (e.g., mvp-e2e)",
    )

    run_parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("data"),
        help="Output root directory (default: data)",
    )

    run_parser.add_argument(
        "--schemas-root",
        type=Path,
        help="Override schemas root directory",
    )

    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show execution plan without running",
    )

    run_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the run command."""
    try:
        result = run_orchestrated_pipeline(
            slate_id=args.slate,
            contest=args.contest,
            seed=args.seed,
            variants_config=args.variants_config,
            optimizer_config=args.optimizer_config,
            sampler_config=args.sampler_config,
            sim_config=args.sim_config,
            tag=args.tag,
            out_root=args.out_root,
            schemas_root=args.schemas_root,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if args.dry_run:
            print(f"[orchestrator] Dry run completed. Plan: {result.get('plan', 'N/A')}")
            return 0

        run_id = result["run_id"]
        artifact_root = result["artifact_root"]
        metrics_head = result.get("metrics_head", {})

        print("[orchestrator] ✓ Run completed successfully")
        print(f"[orchestrator] Run ID: {run_id}")
        print(f"[orchestrator] Artifacts: {artifact_root}")

        if metrics_head:
            roi_mean = metrics_head.get("roi_mean", "N/A")
            roi_p50 = metrics_head.get("roi_p50", "N/A")
            dup_p95 = metrics_head.get("dup_p95", "N/A")
            print(
                f"[orchestrator] Metrics: ROI_mean={roi_mean}, ROI_p50={roi_p50}, dup_p95={dup_p95}"
            )

        return 0

    except Exception as e:
        print(f"[orchestrator] ✗ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "run":
        return cmd_run(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
