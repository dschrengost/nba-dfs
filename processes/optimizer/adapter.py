from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
)

import pandas as pd

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj
from validators import Rules, ValidationResult, validate_lineup

# Resolve repo root (two levels up from this file) and schemas root
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "pipeline" / "schemas"


RunOptimizerFn = Callable[[pd.DataFrame, dict[str, Any], int, str, str], Any]


DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _utc_now_iso() -> str:
    # Millisecond precision per schema pattern
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


def _sha256_of_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_optimizer() -> RunOptimizerFn:
    """Dynamically load the optimizer implementation.

    Tries to import the legacy UI module's run function lazily to avoid bringing
    Streamlit into adapter import time. Tests can monkeypatch this function.
    """
    # Allow override via env var module path: module:function
    override = os.environ.get("OPTIMIZER_IMPL")

    if override:
        mod_name, _, fn_name = override.partition(":")
        mod = __import__(mod_name, fromlist=[fn_name or "run_optimizer"])
        fn = getattr(mod, fn_name or "run_optimizer")
        from typing import cast

        return cast(RunOptimizerFn, fn)

    # Fallback: try legacy location (imports Streamlit inside that module, but
    # only at call time, not at adapter import time)
    try:
        from typing import cast

        from processes.optimizer._legacy.optimize import run_optimizer as _run

        return cast(RunOptimizerFn, _run)
    except (
        Exception
    ) as e:  # pragma: no cover - exercised in smoke tests via monkeypatch
        raise ImportError(
            "No optimizer implementation available. Provide OPTIMIZER_IMPL or monkeypatch _load_optimizer in tests."
        ) from e


def _coerce_scalar(val: str) -> int | float | bool | str:
    lower = val.lower()
    if lower in ("true", "false"):
        return lower == "true"
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


def load_config(
    config_path: Path | None, inline_kv: Sequence[str] | None = None
) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if config_path:
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() in (".yaml", ".yml"):
            import yaml  # lazy

            cfg = dict(yaml.safe_load(text) or {})
        else:
            cfg = dict(json.loads(text))
    if inline_kv:
        for item in inline_kv:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            cfg[k.strip()] = _coerce_scalar(v.strip())
    return cfg


def map_config_to_constraints(config: Mapping[str, Any]) -> dict[str, Any]:
    """Translate user config to the solver constraints dict.

    Unknown keys are preserved (pass-through) to allow downstream expansions; we
    add warnings at call sites if needed.
    """
    c: dict[str, Any] = {}

    # Core
    for key in (
        "num_lineups",
        "max_salary",
        "min_salary",
        "uniques",
        "max_from_team",
        "min_from_team",
        "randomness",
        "position_rules",
    ):
        if key in config:
            c[key] = config[key]

    # Lists
    for key in ("lock", "ban"):
        if key in config:
            c[key] = list(config[key])

    # Nested
    for key in ("exposure_caps", "stacking", "group_rules", "ownership_penalty"):
        if key in config:
            c[key] = config[key]

    # Optional CP-SAT parameters
    for key in ("cp_sat_params", "preset", "dk_strict_mode"):
        if key in config:
            c[key] = config[key]

    return c


def _find_projections(
    slate_id: str,
    in_root: Path,
    explicit_input: Path | None = None,
) -> Path:
    if explicit_input is not None:
        return explicit_input
    # 1) Canonical pointer if present
    candidate_pointer = in_root / "processed" / "current" / "projections.parquet"
    if candidate_pointer.exists():
        return candidate_pointer

    # 2) PRP-1 normalized pattern: data/projections/normalized/<slate_id>__<source>__<updated_ts>.parquet
    normalized_dir = in_root / "projections" / "normalized"
    if normalized_dir.exists():
        matches = sorted(normalized_dir.glob(f"{slate_id}__*.parquet"))
        if matches:
            # Prefer filename tail (updated_ts) first for speed; fallback to reading column
            def tail_key(path: Path) -> str:
                tail = path.stem.split("__")[-1]
                return tail or ""

            keyed: list[tuple[Path, str]] = [(p, tail_key(p)) for p in matches]
            # If any key is empty, fallback to reading updated_ts column for that path
            best: tuple[Path, str] | None = None
            for p, key in keyed:
                if not key:
                    try:
                        ts_col = pd.read_parquet(p, columns=["updated_ts"])
                        key = (
                            str(ts_col["updated_ts"].max()) if not ts_col.empty else ""
                        )
                    except Exception:
                        key = ""
                if not key:
                    key = str(p.stat().st_mtime_ns)
                if best is None or key > best[1]:
                    best = (p, key)
            if best is not None:
                return best[0]

    # 3) Legacy/simple fallbacks
    legacy_candidates = [
        in_root / "projections" / "normalized" / f"{slate_id}.parquet",
        in_root / "projections" / "normalized" / slate_id / "projections.parquet",
        in_root / "processed" / slate_id / "projections.parquet",
    ]
    for p in legacy_candidates:
        if p.exists():
            return p

    looked = (
        [candidate_pointer]
        + (
            [normalized_dir / f"{slate_id}__*.parquet"]
            if normalized_dir.exists()
            else []
        )
        + legacy_candidates
    )
    raise FileNotFoundError(
        f"No projections parquet found for slate_id={slate_id}. Looked in/for: {', '.join(str(p) for p in looked)}"
    )


def _to_solver_df(df: pd.DataFrame) -> pd.DataFrame:
    # Minimal columns expected by solver
    required = ["dk_player_id", "pos", "salary", "proj_fp"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in projections: {missing}")
    # Map to conventional names used by legacy solvers
    out = df.copy()
    out = out.rename(columns={"dk_player_id": "player_id", "pos": "position"})
    return out


def _execute_optimizer(
    projections_df: pd.DataFrame,
    constraints_dict: dict[str, Any],
    seed: int,
    site: str,
    engine: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_opt = _load_optimizer()
    res = run_opt(projections_df, constraints_dict, seed, site, engine)
    # Support either lineups or (lineups, telemetry)
    if isinstance(res, tuple) and len(res) >= 1:
        lineups = list(res[0])
        telemetry = dict(res[1]) if len(res) > 1 and isinstance(res[1], Mapping) else {}
    else:
        lineups = list(res)
        telemetry = {}
    return lineups, telemetry


def export_csv_row(
    players: Sequence[str], dk_positions_filled: Sequence[Mapping[str, Any]]
) -> str:
    """Build DK CSV preview in header order PG,SG,SF,PF,C,G,F,UTIL.

    This is a preview string (not a DK-uploadable row). It expects
    `players[i]` corresponds to `dk_positions_filled[i]` and serializes as
    "<slot> <dk_player_id>" tokens in the canonical slot order.
    """
    slot_to_player: dict[str, str] = {}
    for idx, slot in enumerate(dk_positions_filled):
        slot_to_player[str(slot.get("slot"))] = str(players[idx])
    cols: list[str] = []
    for slot_label in DK_SLOTS_ORDER:
        pid = slot_to_player.get(slot_label, "")
        cols.append(f"{slot_label} {pid}".strip())
    return ",".join(cols)


def _build_player_pool(projections_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Build player pool dict for validator from projections DataFrame."""
    player_pool = {}
    for _, row in projections_df.iterrows():
        dk_player_id = str(row.get("dk_player_id", ""))
        if not dk_player_id:
            continue
        
        # Parse positions - handle both string and list formats
        positions_raw = row.get("pos", "")
        if isinstance(positions_raw, str):
            positions = [p.strip() for p in positions_raw.replace("/", ",").split(",") if p.strip()]
        else:
            positions = list(positions_raw) if positions_raw else []
        
        if not positions:
            positions = ["UTIL"]
        
        player_pool[dk_player_id] = {
            "salary": int(row.get("salary", 0)),
            "positions": positions,
            "team": str(row.get("team", "")),
            "is_active": row.get("is_active", True),
            "inj_status": row.get("inj_status", ""),
        }
    
    return player_pool


def _validate_lineup_with_shared_validator(
    players: Sequence[str],
    player_pool: dict[str, dict[str, Any]],
    rules: Rules,
) -> ValidationResult:
    """Validate lineup using shared validator and raise on error."""
    result = validate_lineup(list(players), player_pool, rules)
    if not result.valid:
        reasons_str = ", ".join([r.value for r in result.reasons])
        raise ValueError(f"Invalid lineup: {reasons_str}")
    return result


def _build_lineups_df(
    run_id: str, lineups: Sequence[Mapping[str, Any]], projections_df: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    # Build player pool for validation
    player_pool = _build_player_pool(projections_df)
    rules = Rules()
    
    # Track validation metrics
    validation_metrics = {
        "total_lineups": len(lineups),
        "valid_lineups": 0,
        "invalid_lineups": 0,
        "reasons_count": {},
    }
    
    rows: list[dict[str, Any]] = []
    for i, lp in enumerate(lineups, start=1):
        players = list(lp.get("players") or [])
        dk_pos = list(lp.get("dk_positions_filled") or [])
        row: dict[str, Any] = {
            "run_id": run_id,
            "lineup_id": f"L{i}",
            "players": players,
            "dk_positions_filled": dk_pos,
            "total_salary": int(lp.get("total_salary", 0)),
            "proj_fp": float(lp.get("proj_fp", 0.0)),
        }
        if "ceil_fp" in lp:
            row["ceil_fp"] = float(lp["ceil_fp"])  # optional
        if "own_proj" in lp:
            row["own_proj"] = float(lp["own_proj"])  # optional
        row["export_csv_row"] = export_csv_row(players, dk_pos)
        
        # Use shared validator
        try:
            validation_result = _validate_lineup_with_shared_validator(players, player_pool, rules)
            validation_metrics["valid_lineups"] += 1
            # Don't add validation fields to row - keep schema compatibility
        except ValueError as e:
            validation_metrics["invalid_lineups"] += 1
            # Track validation failure reasons  
            error_msg = str(e)
            validation_metrics["reasons_count"][error_msg] = validation_metrics["reasons_count"].get(error_msg, 0) + 1
            # Still add the row but track as invalid internally
            
        rows.append(row)
    
    return pd.DataFrame(rows), validation_metrics


def _build_metrics_df(run_id: str, lineups_df: pd.DataFrame) -> pd.DataFrame:
    proj = lineups_df["proj_fp"].astype(float)
    salary = lineups_df["total_salary"].astype(int)
    aggregates = {
        "mean_proj": float(proj.mean()) if not proj.empty else 0.0,
        "median_proj": float(proj.median()) if not proj.empty else 0.0,
        "stdev_proj": float(proj.std(ddof=0)) if len(proj) > 1 else 0.0,
        "salary_utilization_mean": float(salary.mean()) if not salary.empty else 0.0,
    }
    return pd.DataFrame(
        [
            {
                "run_id": run_id,
                "aggregates": aggregates,
                # distributions optional; can be populated later
            }
        ]
    )


def _schema_version(schemas_root: Path | None, name: str) -> str:
    schema = load_schema((schemas_root or SCHEMAS_ROOT) / f"{name}.schema.yaml")
    v = str(schema.get("version", "0.0.0"))
    return v


def run_adapter(
    *,
    slate_id: str,
    site: str,
    config_path: Path | None,
    config_kv: Sequence[str] | None,
    engine: str,
    seed: int,
    out_root: Path,
    tag: str | None = None,
    in_root: Path | None = None,
    input_path: Path | None = None,
    schemas_root: Path | None = None,
) -> dict[str, Any]:
    # Resolve paths and identifiers
    created_ts = _utc_now_iso()

    in_root_eff = in_root or Path("data")
    out_root_eff = out_root

    proj_path = _find_projections(slate_id, in_root_eff, input_path)
    projections_df = pd.read_parquet(proj_path)
    solver_df = _to_solver_df(projections_df)

    # Site preflight (DK only for now)
    if str(site).upper() != "DK":
        raise ValueError(
            f"Unsupported site '{site}'. Only 'DK' is supported in this adapter."
        )

    cfg = load_config(config_path, config_kv)
    constraints = map_config_to_constraints(cfg)

    lineups, telemetry = _execute_optimizer(solver_df, constraints, seed, site, engine)

    # Build manifest inputs and compute run_id (portable with short hash)
    schemas_root = schemas_root or SCHEMAS_ROOT
    manifest_schema = load_schema(schemas_root / "manifest.schema.yaml")

    # Build inputs list: projections + config (file and/or inline overrides)
    proj_sha = _sha256_of_path(proj_path)
    inputs_list: list[dict[str, Any]] = [
        {
            "path": str(proj_path),
            "content_sha256": proj_sha,
            "role": "projections_normalized",
        }
    ]

    # Hash resolved config for determinism
    cfg_json = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    cfg_sha = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    if config_path is not None and config_path.exists():
        inputs_list.append(
            {
                "path": str(config_path),
                "content_sha256": _sha256_of_path(config_path),
                "role": "config",
            }
        )
    if config_kv:
        kv_parsed: dict[str, Any] = {}
        for item in config_kv:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            kv_parsed[k.strip()] = _coerce_scalar(v.strip())
        inputs_list.append(
            {
                "path": "inline:config_kv",
                "content_sha256": hashlib.sha256(
                    json.dumps(kv_parsed, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ).hexdigest(),
                "role": "config",
            }
        )

    # Portable run_id: YYYYMMDD_HHMMSS_<shorthash>
    ts = datetime.now(timezone.utc)
    run_id_core = ts.strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(
        f"{proj_sha}|{cfg_sha}|{seed}|{site}|{engine}".encode()
    ).hexdigest()[:8]
    run_id = f"{run_id_core}_{short_hash}"

    # Now we can build artifacts under the finalized run_id
    run_dir = out_root_eff / "runs" / "optimizer" / run_id
    artifacts_dir = run_dir / "artifacts"
    ensure_dir(artifacts_dir)

    lineups_df, validation_metrics = _build_lineups_df(run_id, lineups, projections_df)
    metrics_df = _build_metrics_df(run_id, lineups_df)
    
    # Write validation metrics
    validation_metrics_path = artifacts_dir / "validation_metrics.json"
    validation_metrics_path.write_text(
        json.dumps(validation_metrics, indent=2), encoding="utf-8"
    )

    # Validate lineups & metrics against their schemas before any write (fail fast)
    lineups_schema = load_schema(schemas_root / "optimizer_lineups.schema.yaml")
    metrics_schema = load_schema(schemas_root / "optimizer_metrics.schema.yaml")
    for row in lineups_df.to_dict(orient="records"):
        validate_obj(lineups_schema, row, schemas_root=schemas_root)
    for row in metrics_df.to_dict(orient="records"):
        validate_obj(metrics_schema, row, schemas_root=schemas_root)

    lineups_path = artifacts_dir / "lineups.parquet"
    metrics_path = artifacts_dir / "metrics.parquet"
    write_parquet(lineups_df, lineups_path)
    write_parquet(metrics_df, metrics_path)

    # Build manifest
    manifest = {
        "schema_version": _schema_version(schemas_root, "manifest"),
        "run_id": run_id,
        "run_type": "optimizer",
        "slate_id": slate_id,
        "created_ts": created_ts,
        "inputs": inputs_list,
        "config": cfg,
        "outputs": [
            {"path": str(lineups_path), "kind": "optimizer_lineups"},
            {"path": str(metrics_path), "kind": "optimizer_metrics"},
        ],
        "tags": [tag] if tag else [],
    }
    # Validate and write manifest.json
    validate_obj(manifest_schema, manifest, schemas_root=schemas_root)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Append registry (validate rows)
    registry_path = out_root_eff / "registry" / "runs.parquet"
    ensure_dir(registry_path.parent)
    reg_row = {
        "run_id": run_id,
        "run_type": "optimizer",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(lineups_path)],
        "metrics_path": str(metrics_path),
        "created_ts": created_ts,
        "tags": [tag] if tag else [],
    }
    runs_registry_schema = load_schema(schemas_root / "runs_registry.schema.yaml")
    validate_obj(runs_registry_schema, reg_row, schemas_root=schemas_root)
    if registry_path.exists():
        existing = pd.read_parquet(registry_path)
        df = pd.concat([existing, pd.DataFrame([reg_row])], ignore_index=True)
    else:
        df = pd.DataFrame([reg_row])
    write_parquet(df, registry_path)

    return {
        "run_id": run_id,
        "lineups_path": str(lineups_path),
        "metrics_path": str(metrics_path),
        "manifest_path": str(run_dir / "manifest.json"),
        "registry_path": str(registry_path),
        "lineup_count": int(len(lineups_df)),
        "projections_path": str(proj_path),
        "telemetry": telemetry,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.optimizer")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--site", default="DK")
    p.add_argument("--config", type=Path)
    p.add_argument("--config-kv", nargs="*", help="Inline overrides key=value")
    p.add_argument("--engine", default="cbc")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--tag", type=str)
    p.add_argument("--in-root", type=Path, default=Path("data"))
    p.add_argument("--input", type=Path, help="Explicit projections parquet path")
    p.add_argument(
        "--schemas-root",
        type=Path,
        help="Override schemas root (defaults to repo-relative pipeline/schemas)",
    )
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    # Basic unknown key warning when verbose
    result = run_adapter(
        slate_id=args.slate_id,
        site=str(args.site),
        config_path=args.config,
        config_kv=args.config_kv,
        engine=str(args.engine),
        seed=int(args.seed),
        out_root=args.out_root,
        tag=args.tag,
        in_root=args.in_root,
        input_path=args.input,
        schemas_root=args.schemas_root,
    )
    if args.verbose:
        # Warn if config contains keys not in known constraints
        known = {
            "num_lineups",
            "max_salary",
            "min_salary",
            "uniques",
            "max_from_team",
            "min_from_team",
            "randomness",
            "position_rules",
            "lock",
            "ban",
            "exposure_caps",
            "stacking",
            "group_rules",
            "ownership_penalty",
            "cp_sat_params",
            "preset",
            "dk_strict_mode",
        }
        cfg = load_config(args.config, args.config_kv)
        unknown = sorted(set(cfg.keys()) - known)
        if unknown:
            print(
                f"[optimizer] Warning: unknown config keys ignored/passthrough: {', '.join(unknown)}",
                file=sys.stderr,
            )
        print(
            f"[optimizer] projections: {result.get('projections_path')}",
            file=sys.stderr,
        )
        print(f"[optimizer] manifest: {result.get('manifest_path')}", file=sys.stderr)
        print(
            f"[optimizer] lineups written: {result.get('lineup_count')}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
