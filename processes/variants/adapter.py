from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj

# Resolve repo root (two levels up from this file) and schemas root
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "pipeline" / "schemas"


RunVariantFn = Callable[[pd.DataFrame, dict[str, Any], int], Any]

DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _utc_now_iso() -> str:
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


def _as_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def _as_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _sha256_of_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _load_variant() -> RunVariantFn:
    """Dynamically load the variant implementation.

    Tests can monkeypatch this function. By default, this loader uses the
    `OPTIMIZER_VARIANT_IMPL=module:function` override if present, otherwise
    raises ImportError.
    """
    override = os.environ.get("OPTIMIZER_VARIANT_IMPL")
    if override:
        mod_name, _, fn_name = override.partition(":")
        mod = __import__(mod_name, fromlist=[fn_name or "run_variants"])
        fn = getattr(mod, fn_name or "run_variants")
        from typing import cast

        return cast(RunVariantFn, fn)

    # No built-in fallback here; adapter is headless
    raise ImportError(
        "No variant implementation available. Provide OPTIMIZER_VARIANT_IMPL or "
        "monkeypatch _load_variant in tests."
    )


def load_config(
    config_path: Path | None, inline_kv: Sequence[str] | None = None
) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if config_path:
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() in (".yaml", ".yml"):
            import yaml  # lazy

            try:
                cfg = dict(yaml.safe_load(text) or {})
            except Exception as e:  # pragma: no cover - error path exercised in tests
                msg = f"Failed to parse YAML config {config_path}: {e}"
                raise ValueError(msg) from e
        else:
            cfg = dict(json.loads(text))
    if inline_kv:
        for item in inline_kv:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            cfg[k.strip()] = _coerce_scalar(v.strip())
    return cfg


def map_config_to_knobs(config: Mapping[str, Any]) -> dict[str, Any]:
    """Translate user config to variant knobs.

    Unknown keys are preserved/pass-through so downstream implementations can
    consume them. This function primarily validates and normalizes known keys.
    """
    c: dict[str, Any] = {}
    for key in (
        "num_variants",
        "swap_window",
        "randomness",
        "exposure_targets",
        "group_rules",
        "uniques",
        "avoid_dups",
        "ownership_guidance",
        "seed",
    ):
        if key in config:
            c[key] = config[key]
    # Preserve extras
    for k, v in config.items():
        if k not in c:
            c.setdefault("extras", {})[k] = v
    return c


def export_csv_row(
    players: Sequence[str], dk_positions_filled: Sequence[Mapping[str, Any]]
) -> str:
    slot_to_player: dict[str, str] = {}
    for idx, slot in enumerate(dk_positions_filled):
        slot_to_player[str(slot.get("slot"))] = str(players[idx])
    cols: list[str] = []
    for slot_label in DK_SLOTS_ORDER:
        pid = slot_to_player.get(slot_label, "")
        cols.append(f"{slot_label} {pid}".strip())
    return ",".join(cols)


def _sanity_check_variant(players: Sequence[Any]) -> None:
    if len(players) != 8:
        raise ValueError(f"Invalid variant: expected 8 players, got {len(players)}")


def _find_input_optimizer_lineups(
    *,
    out_root: Path,
    slate_id: str,
    explicit_input: Path | None = None,
    from_run: str | None = None,
) -> Path:
    if explicit_input is not None:
        return explicit_input
    # If a specific run_id provided, use that run dir
    if from_run:
        candidate = (
            out_root / "runs" / "optimizer" / from_run / "artifacts" / "lineups.parquet"
        )
        if candidate.exists():
            return candidate
        raise FileNotFoundError(
            f"--from-run provided but lineups not found: {candidate}"
        )
    # Otherwise, consult registry for latest optimizer run for this slate
    registry_path = out_root / "registry" / "runs.parquet"
    if registry_path.exists():
        df = pd.read_parquet(registry_path)
        required_cols = {"run_type", "slate_id", "created_ts"}
        if not required_cols.issubset(set(map(str, df.columns))):
            missing = sorted(required_cols - set(map(str, df.columns)))
            raise ValueError(
                f"Registry missing required columns {missing}. "
                "Re-run optimizer to populate registry."
            )
        filt = df[
            (df.get("run_type") == "optimizer") & (df.get("slate_id") == slate_id)
        ]
        if not filt.empty:
            # pick latest by created_ts lexicographically (ISO format)
            idx = filt["created_ts"].astype(str).idxmax()
            row = df.loc[idx]
            # Use primary_outputs[0] if available, else construct from run_id
            try:
                primary = row.get("primary_outputs")
                if isinstance(primary, list) and primary:
                    p0 = Path(primary[0])
                    return p0 if p0.is_absolute() else (out_root / primary[0])
            except Exception:
                pass
            run_id = str(row.get("run_id"))
            opt_runs = out_root / "runs" / "optimizer"
            candidate = opt_runs / run_id / "artifacts" / "lineups.parquet"
            if candidate.exists():
                return candidate
    raise FileNotFoundError(
        "No optimizer lineups found for slate_id="
        f"{slate_id}. Provide --input or --from-run."
    )


def _schema_version(schemas_root: Path | None, name: str) -> str:
    schema = load_schema((schemas_root or SCHEMAS_ROOT) / f"{name}.schema.yaml")
    return str(schema.get("version", "0.0.0"))


def _build_variant_catalog(
    run_id: str,
    variants: Sequence[Mapping[str, Any]],
    parent_lineups_df: pd.DataFrame,
) -> pd.DataFrame:
    parent_map = {
        str(row["lineup_id"]): {
            "players": list(row["players"]),
            "dk_positions_filled": list(row["dk_positions_filled"]),
            "total_salary": _as_int(row.get("total_salary", 0)),
            "proj_fp": _as_float(row.get("proj_fp", 0.0)),
        }
        for _, row in parent_lineups_df.iterrows()
    }
    rows: list[dict[str, Any]] = []
    for i, v in enumerate(variants, start=1):
        players = list(v.get("players") or [])
        _sanity_check_variant(players)
        # Duplicate player guard
        if len(set(map(str, players))) != 8:
            raise ValueError("Invalid variant: duplicate players detected")
        parent_id = str(v.get("parent_lineup_id") or v.get("parent_id") or "")
        if not parent_id or parent_id not in parent_map:
            raise ValueError(f"Variant missing/unknown parent_lineup_id: {parent_id}")
        parent = parent_map[parent_id]
        dk_pos = cast(Sequence[Mapping[str, Any]], parent["dk_positions_filled"]) 
        if len(dk_pos) != 8:
            raise ValueError("Parent lineup DK slots invalid (expected 8)")
        row: dict[str, Any] = {
            "run_id": run_id,
            "variant_id": str(v.get("variant_id") or f"V{i}"),
            "parent_lineup_id": parent_id,
            "players": players,
            "variant_params": dict(v.get("variant_params") or {}),
            "export_csv_row": export_csv_row(players, dk_pos),
        }
        # Salary cap check if provided on variant
        if "total_salary" in v:
            try:
                _ts = int(v["total_salary"])  # may raise
            except Exception:
                _ts = None
            if _ts is not None and _ts > 50000:
                raise ValueError("Invalid variant: salary exceeds DK cap 50000")
        # Optional fields if provided or derivable
        if "hamming_vs_parent" in v:
            row["hamming_vs_parent"] = int(v["hamming_vs_parent"])  # pragma: no cover
        else:
            try:
                parent_players = cast(Sequence[Any], parent["players"]) 
                hamming = sum(
                    1 for a, b in zip(list(players), list(parent_players), strict=False) if a != b
                )
                row["hamming_vs_parent"] = int(hamming)
            except Exception:
                pass
        if "salary_delta" in v:
            row["salary_delta"] = int(v["salary_delta"])  # pragma: no cover
        else:
            row["salary_delta"] = _as_int(v.get("total_salary", 0)) - _as_int(
                parent.get("total_salary", 0)
            )
        # If we can derive a variant total, enforce cap as a second-line check
        var_total = _as_int(parent.get("total_salary", 0)) + _as_int(
            row.get("salary_delta", 0)
        )
        if var_total is not None and var_total > 50000:
            raise ValueError("Invalid variant: salary exceeds DK cap 50000")
        if "proj_delta" in v:
            row["proj_delta"] = float(v["proj_delta"])  # pragma: no cover
        else:
            row["proj_delta"] = _as_float(v.get("proj_fp", 0.0)) - _as_float(
                parent.get("proj_fp", 0.0)
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _build_variant_metrics(run_id: str, catalog_df: pd.DataFrame) -> pd.DataFrame:
    # Simple aggregates: approximate entropy via unique variant players diversity,
    # chalk index as max per-player inclusion rate.
    player_counts: dict[str, int] = {}
    total_variants = int(len(catalog_df))
    for players in catalog_df["players"]:
        for p in players:
            player_counts[p] = player_counts.get(p, 0) + 1
    if total_variants > 0 and player_counts:
        rates = [c / (total_variants) for c in player_counts.values()]
        chalk_index = float(max(rates))
        # Shannon-like proxy (not true entropy over lineup space):
        import math

        entropy = float(-sum(r * math.log(r + 1e-12) for r in rates if r > 0.0))
        if entropy < 0:
            entropy = 0.0
    else:
        chalk_index = 0.0
        entropy = 0.0
    aggregates = {"chalk_index": chalk_index, "entropy": entropy}
    return pd.DataFrame([{"run_id": run_id, "aggregates": aggregates}])


def run_adapter(
    *,
    slate_id: str,
    config_path: Path | None,
    config_kv: Sequence[str] | None,
    seed: int,
    out_root: Path,
    tag: str | None,
    input_path: Path | None,
    from_run: str | None = None,
    schemas_root: Path | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    created_ts = _utc_now_iso()
    out_root_eff = out_root

    opt_lineups_path = _find_input_optimizer_lineups(
        out_root=out_root_eff,
        slate_id=slate_id,
        explicit_input=input_path,
        from_run=from_run,
    )
    parent_lineups_df = pd.read_parquet(opt_lineups_path)

    cfg = load_config(config_path, config_kv)
    knobs = map_config_to_knobs(cfg)
    # Seed precedence: function arg takes precedence; include in knobs for compatibility
    knobs["seed"] = seed

    # Execute variant builder
    run_variants = _load_variant()
    res = run_variants(parent_lineups_df, knobs, seed)
    if isinstance(res, tuple) and len(res) >= 1:
        variants = list(res[0])
        telemetry = dict(res[1]) if len(res) > 1 and isinstance(res[1], Mapping) else {}
    else:
        variants = list(res)
        telemetry = {}

    # Early sanity: salary cap if present on variant objects
    for _v in variants:
        if isinstance(_v, Mapping) and "total_salary" in _v:
            try:
                _ts = int(_v["total_salary"])  # may raise
            except Exception:
                _ts = None
            if _ts is not None and _ts > 50000:
                raise ValueError("Invalid variant: salary exceeds DK cap 50000")

    schemas_root = schemas_root or SCHEMAS_ROOT
    manifest_schema = load_schema(schemas_root / "manifest.schema.yaml")

    # Build inputs: optimizer lineups + config(s)
    opt_sha = _sha256_of_path(opt_lineups_path)
    inputs_list: list[dict[str, Any]] = [
        {
            "path": str(opt_lineups_path),
            "content_sha256": opt_sha,
            "role": "optimizer_lineups",
        }
    ]
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

    # Deterministic run_id
    ts = datetime.now(timezone.utc)
    run_id_core = ts.strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(f"{opt_sha}|{cfg_sha}|{seed}".encode()).hexdigest()[:8]
    run_id = f"{run_id_core}_{short_hash}"

    # Build artifacts
    run_dir = out_root_eff / "runs" / "variants" / run_id
    artifacts_dir = run_dir / "artifacts"
    ensure_dir(artifacts_dir)

    catalog_df = _build_variant_catalog(run_id, variants, parent_lineups_df)
    metrics_df = _build_variant_metrics(run_id, catalog_df)

    # Validate rows against schemas (fail fast) unless disabled
    if validate:
        catalog_schema = load_schema(schemas_root / "variant_catalog.schema.yaml")
        metrics_schema = load_schema(schemas_root / "variant_metrics.schema.yaml")
        for row in catalog_df.to_dict(orient="records"):
            validate_obj(catalog_schema, row, schemas_root=schemas_root)
        for row in metrics_df.to_dict(orient="records"):
            validate_obj(metrics_schema, row, schemas_root=schemas_root)

    # Parquet compatibility: ensure variant_params isn't an empty struct which
    # pyarrow can't write (struct with no fields). Replace {} with {"_": None}.
    if "variant_params" in catalog_df.columns:
        catalog_df["variant_params"] = catalog_df["variant_params"].apply(
            lambda x: x if isinstance(x, dict) and len(x) > 0 else {"_": None}
        )

    catalog_path = artifacts_dir / "variant_catalog.parquet"
    metrics_path = artifacts_dir / "metrics.parquet"
    write_parquet(catalog_df, catalog_path)
    write_parquet(metrics_df, metrics_path)

    # Manifest
    manifest = {
        "schema_version": _schema_version(schemas_root, "manifest"),
        "run_id": run_id,
        "run_type": "variants",
        "slate_id": slate_id,
        "created_ts": created_ts,
        "inputs": inputs_list,
        "config": cfg,
        "outputs": [
            {"path": str(catalog_path), "kind": "variant_catalog"},
            {"path": str(metrics_path), "kind": "variant_metrics"},
        ],
        "tags": [tag] if tag else [],
    }
    if validate:
        validate_obj(manifest_schema, manifest, schemas_root=schemas_root)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Registry append
    registry_path = out_root_eff / "registry" / "runs.parquet"
    ensure_dir(registry_path.parent)
    reg_row = {
        "run_id": run_id,
        "run_type": "variants",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(catalog_path)],
        "metrics_path": str(metrics_path),
        "created_ts": created_ts,
        "tags": [tag] if tag else [],
    }
    if validate:
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
        "catalog_path": str(catalog_path),
        "metrics_path": str(metrics_path),
        "manifest_path": str(run_dir / "manifest.json"),
        "registry_path": str(registry_path),
        "variant_count": int(len(catalog_df)),
        "optimizer_lineups_path": str(opt_lineups_path),
        "telemetry": telemetry,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.variants")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--config-kv", nargs="*", help="Inline overrides key=value")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--tag", type=str)
    p.add_argument("--input", type=Path, help="Explicit optimizer lineups parquet path")
    p.add_argument(
        "--from-run",
        type=str,
        help="Optimizer run_id to source lineups from (run_type=optimizer)",
    )
    p.add_argument(
        "--schemas-root",
        type=Path,
        help="Override schemas root (defaults to repo-relative pipeline/schemas)",
    )
    p.add_argument("--no-validate", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_adapter(
        slate_id=args.slate_id,
        config_path=args.config,
        config_kv=args.config_kv,
        seed=int(args.seed),
        out_root=args.out_root,
        tag=args.tag,
        input_path=args.input,
        from_run=args.from_run,
        schemas_root=args.schemas_root,
        validate=not args.no_validate,
    )
    if args.verbose:
        known = {
            "num_variants",
            "swap_window",
            "randomness",
            "exposure_targets",
            "group_rules",
            "uniques",
            "avoid_dups",
            "ownership_guidance",
            "seed",
        }
        cfg = load_config(args.config, args.config_kv)
        unknown = sorted(set(cfg.keys()) - known - {"extras"})
        if unknown:
            unk_msg = ", ".join(unknown)
            print(
                "[variants] Warning: unknown config keys ignored/passthrough: "
                f"{unk_msg}",
                file=sys.stderr,
            )
        print(
            (
                "[variants] input="
                f"{result.get('optimizer_lineups_path')} "
                f"run_id={result.get('run_id')} "
                f"variants={result.get('variant_count')}"
            ),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
