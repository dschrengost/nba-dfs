from __future__ import annotations

"""Core orchestration logic for end-to-end pipeline execution."""

import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj
from processes.field_sampler import adapter as field_sampler_adapter
from processes.gpp_sim import adapter as gpp_sim_adapter
from processes.optimizer import adapter as optimizer_adapter
from processes.variants import adapter as variants_adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "pipeline" / "schemas"


def _utc_now_iso() -> str:
    """Generate UTC timestamp in ISO format with millisecond precision."""
    now = datetime.now(UTC)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


def _get_git_rev() -> str:
    """Get current git HEAD short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _make_run_id(seed: int, slate_id: str, contest: str) -> str:
    """Generate run_id in PRP format: YYYYMMDD-HHMMSS-<shorthash>."""
    now = datetime.now(UTC)
    ts_part = now.strftime("%Y%m%d-%H%M%S")

    # Create hash from seed + slate + contest for determinism
    hash_input = f"{seed}|{slate_id}|{contest}|{now.isoformat()}"
    short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

    return f"{ts_part}-{short_hash}"


def _load_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from YAML or JSON file."""
    text = config_path.read_text(encoding="utf-8")

    if config_path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        return dict(yaml.safe_load(text) or {})
    else:
        return dict(json.loads(text))


def _set_global_seed(seed: int) -> None:
    """Set global random seeds for reproducibility."""
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def _export_dk_csv(lineups_df: pd.DataFrame, output_path: Path) -> None:
    """Export lineups to DraftKings CSV format."""
    # DK expects specific column headers
    dk_columns = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]

    # Build CSV rows from lineup data
    csv_rows = []
    csv_rows.append(",".join(dk_columns))  # Header

    for _, row in lineups_df.iterrows():
        players = list(row["players"])
        dk_positions = list(row["dk_positions_filled"])

        # Map positions to players
        position_map = {}
        for i, pos_info in enumerate(dk_positions):
            slot = pos_info.get("slot")
            if slot and i < len(players):
                position_map[slot] = str(players[i])

        # Build row in correct order
        dk_row = []
        for col in dk_columns:
            player_id = position_map.get(col, "")
            dk_row.append(player_id)

        csv_rows.append(",".join(dk_row))

    output_path.write_text("\n".join(csv_rows), encoding="utf-8")


def _compute_sim_metrics(sim_results_df: pd.DataFrame) -> dict[str, Any]:
    """Compute high-level metrics from simulation results."""
    if sim_results_df.empty:
        return {
            "roi_mean": 0.0,
            "roi_p50": 0.0,
            "dup_p95": 0.0,
            "finish_percentiles": [],
        }

    # Basic ROI metrics
    roi_values = sim_results_df.get("roi", pd.Series(dtype=float))
    if not roi_values.empty:
        roi_mean = float(roi_values.mean())
        roi_p50 = float(roi_values.median())
    else:
        roi_mean = roi_p50 = 0.0

    # Duplication analysis (placeholder)
    dup_p95 = 0.0  # TODO: Implement duplication analysis

    # Finish percentiles (placeholder)
    finish_percentiles = []  # TODO: Implement finish percentile analysis

    return {
        "roi_mean": roi_mean,
        "roi_p50": roi_p50,
        "dup_p95": dup_p95,
        "finish_percentiles": finish_percentiles,
    }


def _write_summary_markdown(
    run_id: str,
    slate_id: str,
    contest: str,
    metrics: dict[str, Any],
    timings: dict[str, Any],
    output_path: Path,
) -> None:
    """Write human-readable summary in Markdown format."""
    content = f"""# Run Summary

**Run ID:** `{run_id}`  
**Slate:** `{slate_id}`  
**Contest:** `{contest}`  
**Generated:** {_utc_now_iso()}

## Key Metrics

- **ROI Mean:** {metrics.get('roi_mean', 'N/A'):.3f}
- **ROI Median:** {metrics.get('roi_p50', 'N/A'):.3f}
- **Duplication P95:** {metrics.get('dup_p95', 'N/A'):.3f}

## Performance

- **Total Duration:** {timings.get('total_duration_ms', 0):,}ms
- **Variants:** {timings.get('variants_duration_ms', 0):,}ms  
- **Optimizer:** {timings.get('optimizer_duration_ms', 0):,}ms
- **Field Sampler:** {timings.get('field_sampler_duration_ms', 0):,}ms
- **GPP Sim:** {timings.get('gpp_sim_duration_ms', 0):,}ms

## Artifacts

All artifacts are stored under the run directory with this run_id.
"""

    output_path.write_text(content, encoding="utf-8")


def _resolve_contest_input(contest: str, out_root: Path) -> tuple[Path | None, Path | None]:
    """Resolve contest identifier to a file path or directory.

    The ``contest`` argument may be either an explicit path to a contest file
    (csv/parquet/json) or a slug that corresponds to a directory or file under
    ``out_root/contests``. The gpp simulator requires at least one of
    ``contest_path`` or ``from_contest_dir`` to locate the contest structure.

    Parameters
    ----------
    contest:
        Contest identifier or path provided by the user.
    out_root:
        Root output directory where contest resources may reside.

    Returns
    -------
    tuple[Path | None, Path | None]
        A tuple of ``(contest_path, from_contest_dir)`` suitable for forwarding
        to ``gpp_sim_adapter.run_adapter``.

    Raises
    ------
    FileNotFoundError
        If no contest file or directory can be resolved.
    """

    candidate = Path(contest)
    if candidate.exists():
        if candidate.is_dir():
            return None, candidate
        return candidate, None

    base = out_root / "contests"
    dir_candidate = base / contest
    if dir_candidate.is_dir():
        return None, dir_candidate

    for suffix in (".csv", ".parquet", ".json"):
        file_candidate = base / f"{contest}{suffix}"
        if file_candidate.exists():
            return file_candidate, None

    raise FileNotFoundError(f"Contest input for '{contest}' not found under {base}")


def run_orchestrated_pipeline(
    *,
    slate_id: str,
    contest: str,
    seed: int,
    variants_config: Path,
    optimizer_config: Path,
    sampler_config: Path,
    sim_config: Path,
    tag: str | None = None,
    out_root: Path = Path("data"),
    schemas_root: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Execute the complete orchestrated pipeline.

    This implements the core logic from the PRP pseudocode:
    1. Resolve context (slate, configs)
    2. Generate variant catalog
    3. Run optimizer with catalog
    4. Sample field from lineups
    5. Run GPP simulation
    6. Compute metrics and write artifacts
    7. Update runs registry
    """
    start_time = time.time()
    schemas_root = schemas_root or SCHEMAS_ROOT

    # Generate run_id upfront
    run_id = _make_run_id(seed, slate_id, contest)

    if dry_run:
        plan = [
            f"1. Generate variants from config: {variants_config}",
            f"2. Run optimizer with config: {optimizer_config}",
            f"3. Sample field with config: {sampler_config}",
            f"4. Run GPP simulation with config: {sim_config}",
            f"5. Write artifacts under run_id: {run_id}",
            f"6. Update registry with tag: {tag or 'none'}",
        ]
        return {"run_id": run_id, "plan": plan}

    if verbose:
        print(f"[orchestrator] Starting run_id={run_id}")
        print(f"[orchestrator] Slate: {slate_id}, Contest: {contest}, Seed: {seed}")

    # Set global seed for reproducibility
    _set_global_seed(seed)

    # Create run directory structure per PRP artifact layout
    run_dir = out_root / "runs" / slate_id / run_id
    variants_dir = run_dir / "variants"
    optimizer_dir = run_dir / "optimizer"
    field_dir = run_dir / "field_sampler"
    sim_dir = run_dir / "sim"
    export_dir = run_dir / "export"

    for dir_path in [variants_dir, optimizer_dir, field_dir, sim_dir, export_dir]:
        ensure_dir(dir_path)

    # Load configurations
    variants_cfg = _load_config(variants_config)
    optimizer_cfg = _load_config(optimizer_config)
    sampler_cfg = _load_config(sampler_config)
    sim_cfg = _load_config(sim_config)

    # Track timings for each stage
    timings = {}
    modules = {}

    # Stage 1: Variants
    if verbose:
        print("[orchestrator] Stage 1: Generating variants...")
    stage_start = time.time()

    # NOTE: This assumes we have projections and optimizer lineups ready.
    # In a real implementation, we'd need to ensure the prerequisite data exists
    # or run the ingest/optimizer stages first.

    # For now, we'll run a minimal optimizer first to get lineups for variants
    opt_result = optimizer_adapter.run_adapter(
        slate_id=slate_id,
        site="DK",
        config_path=optimizer_config,
        config_kv=None,
        engine="cbc",
        seed=seed,
        out_root=out_root,
        tag=f"orch:{run_id}",
        schemas_root=schemas_root,
    )

    optimizer_run_id = opt_result["run_id"]
    timings["optimizer_duration_ms"] = int((time.time() - stage_start) * 1000)
    modules["optimizer"] = {
        "version": _get_git_rev(),
        "run_id": optimizer_run_id,
        "manifest_path": opt_result["manifest_path"],
        "config": optimizer_cfg,
    }

    if verbose:
        print(f"[orchestrator] ✓ Optimizer completed: {optimizer_run_id}")

    # Now run variants
    stage_start = time.time()
    var_result = variants_adapter.run_adapter(
        slate_id=slate_id,
        config_path=variants_config,
        config_kv=None,
        seed=seed,
        out_root=out_root,
        tag=f"orch:{run_id}",
        from_run=optimizer_run_id,
        schemas_root=schemas_root,
    )

    variants_run_id = var_result["run_id"]
    timings["variants_duration_ms"] = int((time.time() - stage_start) * 1000)
    modules["variants"] = {
        "version": _get_git_rev(),
        "run_id": variants_run_id,
        "manifest_path": var_result["manifest_path"],
        "config": variants_cfg,
    }

    if verbose:
        print(f"[orchestrator] ✓ Variants completed: {variants_run_id}")

    # Stage 2: Field Sampler
    if verbose:
        print("[orchestrator] Stage 2: Sampling field...")
    stage_start = time.time()

    field_result = field_sampler_adapter.run_adapter(
        slate_id=slate_id,
        config_path=sampler_config,
        config_kv=None,
        seed=seed,
        out_root=out_root,
        tag=f"orch:{run_id}",
        from_run=variants_run_id,
        schemas_root=schemas_root,
    )

    field_run_id = field_result["run_id"]
    timings["field_sampler_duration_ms"] = int((time.time() - stage_start) * 1000)
    modules["field_sampler"] = {
        "version": _get_git_rev(),
        "run_id": field_run_id,
        "manifest_path": field_result["manifest_path"],
        "config": sampler_cfg,
    }

    if verbose:
        print(f"[orchestrator] ✓ Field sampler completed: {field_run_id}")

    # Stage 3: GPP Simulation
    if verbose:
        print("[orchestrator] Stage 3: Running GPP simulation...")
    stage_start = time.time()

    contest_path, contest_dir = _resolve_contest_input(contest, out_root)
    sim_result = gpp_sim_adapter.run_adapter(
        slate_id=slate_id,
        config_path=sim_config,
        config_kv=None,
        seed=seed,
        out_root=out_root,
        tag=f"orch:{run_id}",
        from_field_run=field_run_id,
        field_path=None,
        variants_path=None,
        contest_path=contest_path,
        from_contest_dir=contest_dir,
        schemas_root=schemas_root,
        verbose=verbose,
    )

    sim_run_id = sim_result["run_id"]
    timings["gpp_sim_duration_ms"] = int((time.time() - stage_start) * 1000)
    modules["gpp_sim"] = {
        "version": _get_git_rev(),
        "run_id": sim_run_id,
        "manifest_path": sim_result["manifest_path"],
        "config": sim_cfg,
    }

    if verbose:
        print(f"[orchestrator] ✓ GPP simulation completed: {sim_run_id}")

    # Stage 4: Compute metrics and create artifacts per PRP layout
    if verbose:
        print("[orchestrator] Stage 4: Computing metrics and creating artifacts...")

    # Copy/link artifacts to expected PRP locations
    optimizer_lineups_path = optimizer_dir / "lineups.parquet"
    optimizer_dk_export_path = optimizer_dir / "dk_export.csv"
    optimizer_metrics_path = optimizer_dir / "metrics.json"

    field_entrants_path = field_dir / "entrants.parquet"
    field_telemetry_path = field_dir / "telemetry.json"
    field_metrics_path = field_dir / "metrics.json"

    sim_results_path = sim_dir / "results.parquet"
    sim_metrics_path = sim_dir / "metrics.json"

    summary_path = export_dir / "summary.md"

    # Copy optimizer artifacts
    opt_lineups_src = Path(opt_result["lineups_path"])
    opt_lineups_df = pd.read_parquet(opt_lineups_src)
    write_parquet(opt_lineups_df, optimizer_lineups_path)

    # Export DK CSV
    _export_dk_csv(opt_lineups_df, optimizer_dk_export_path)

    # Copy metrics files (simplified - in real implementation, these would be computed)
    opt_metrics_src = Path(opt_result["metrics_path"])
    opt_metrics_df = pd.read_parquet(opt_metrics_src)
    opt_metrics_data = (
        opt_metrics_df.to_dict(orient="records")[0] if not opt_metrics_df.empty else {}
    )
    optimizer_metrics_path.write_text(json.dumps(opt_metrics_data, indent=2), encoding="utf-8")

    # Copy field artifacts
    field_src = Path(field_result["field_path"])
    field_df = pd.read_parquet(field_src)
    write_parquet(field_df, field_entrants_path)

    # Telemetry and metrics (simplified)
    field_telemetry = field_result.get("telemetry", {})
    field_telemetry_path.write_text(json.dumps(field_telemetry, indent=2), encoding="utf-8")

    field_metrics_data = {"placeholder": "field_metrics"}
    field_metrics_path.write_text(json.dumps(field_metrics_data, indent=2), encoding="utf-8")

    # Copy sim artifacts
    sim_src = Path(sim_result["sim_results_path"])
    sim_df = pd.read_parquet(sim_src)
    write_parquet(sim_df, sim_results_path)

    # Compute final metrics
    sim_metrics = _compute_sim_metrics(sim_df)
    sim_metrics_path.write_text(json.dumps(sim_metrics, indent=2), encoding="utf-8")

    # Total timing
    total_duration_ms = int((time.time() - start_time) * 1000)
    timings["total_duration_ms"] = total_duration_ms

    # Write summary
    _write_summary_markdown(run_id, slate_id, contest, sim_metrics, timings, summary_path)

    # Stage 5: Create run manifest
    manifest = {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "slate_id": slate_id,
        "created_ts": _utc_now_iso(),
        "contest": contest,
        "tag": tag,
        "modules": modules,
        "seeds": {
            "global": seed,
            "variants": seed,
            "optimizer": seed,
            "field_sampler": seed,
            "gpp_sim": seed,
        },
        "artifact_paths": {
            "variants_catalog": str(var_result["catalog_path"]),
            "optimizer_lineups": str(optimizer_lineups_path),
            "optimizer_dk_export": str(optimizer_dk_export_path),
            "optimizer_metrics": str(optimizer_metrics_path),
            "field_entrants": str(field_entrants_path),
            "field_telemetry": str(field_telemetry_path),
            "field_metrics": str(field_metrics_path),
            "sim_results": str(sim_results_path),
            "sim_metrics": str(sim_metrics_path),
            "summary": str(summary_path),
        },
        "timings": timings,
        "git_rev": _get_git_rev(),
    }

    # Validate manifest against schema
    manifest_schema = load_schema(schemas_root / "run_manifest.schema.yaml")
    validate_obj(manifest_schema, manifest, schemas_root=schemas_root)

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Stage 6: Update runs registry
    registry_path = out_root / "registry" / "runs.parquet"
    ensure_dir(registry_path.parent)
    reg_row = {
        "run_id": run_id,
        "run_type": "orchestrated",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(summary_path)],
        "metrics_path": str(sim_metrics_path),
        "created_ts": _utc_now_iso(),
        "tags": [tag] if tag else [],
    }

    # Validate against registry schema
    runs_registry_schema = load_schema(schemas_root / "runs_registry.schema.yaml")
    validate_obj(runs_registry_schema, reg_row, schemas_root=schemas_root)

    # Append to registry
    if registry_path.exists():
        existing = pd.read_parquet(registry_path)
        df = pd.concat([existing, pd.DataFrame([reg_row])], ignore_index=True)
    else:
        df = pd.DataFrame([reg_row])
    write_parquet(df, registry_path)

    if verbose:
        print(f"[orchestrator] ✓ Run completed in {total_duration_ms:,}ms")

    return {
        "run_id": run_id,
        "artifact_root": str(run_dir),
        "manifest_path": str(manifest_path),
        "metrics_head": {
            "roi_mean": sim_metrics.get("roi_mean"),
            "roi_p50": sim_metrics.get("roi_p50"),
            "dup_p95": sim_metrics.get("dup_p95"),
        },
    }
