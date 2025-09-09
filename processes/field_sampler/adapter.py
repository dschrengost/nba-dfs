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


RunFieldSamplerFn = Callable[[pd.DataFrame, dict[str, Any], int], Any]

DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


def _utc_now_iso() -> str:
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


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


def _load_sampler() -> RunFieldSamplerFn:
    """Dynamically load the field sampler implementation.

    Use `FIELD_SAMPLER_IMPL=module:function` to override. Tests may monkeypatch
    this loader. By default, this adapter is headless and will raise unless an
    implementation is provided.
    """
    override = os.environ.get("FIELD_SAMPLER_IMPL")
    if override:
        mod_name, _, fn_name = override.partition(":")
        mod = __import__(mod_name, fromlist=[fn_name or "run_sampler"])
        fn = getattr(mod, fn_name or "run_sampler")
        return cast(RunFieldSamplerFn, fn)

    from field_sampler.engine import run_sampler as default_sampler

    return cast(RunFieldSamplerFn, default_sampler)


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
    """Translate user config to field sampler knobs.

    Unknown keys are preserved under `extras` for downstream consumers.
    """
    c: dict[str, Any] = {}
    for key in (
        "field_size",
        "source_mix",
        "sampling_mode",
        "ownership_curve",
        "diversity",
        "team_limits",
        "de-dup",
        "seed",
    ):
        if key in config:
            c[key] = config[key]
    # Preserve extras
    for k, v in config.items():
        if k not in c:
            c.setdefault("extras", {})[k] = v
    return c


def _find_input_variant_catalog(
    *,
    out_root: Path,
    slate_id: str,
    explicit_input: Path | None = None,
    from_run: str | None = None,
    inputs: Sequence[Path] | None = None,
) -> list[Path]:
    if inputs:
        return list(inputs)
    if explicit_input is not None:
        return [explicit_input]
    if from_run:
        candidate = (
            out_root
            / "runs"
            / "variants"
            / from_run
            / "artifacts"
            / "variant_catalog.parquet"
        )
        if candidate.exists():
            return [candidate]
        raise FileNotFoundError(
            f"--from-run provided but variant_catalog not found: {candidate}"
        )
    registry_path = out_root / "registry" / "runs.parquet"
    if registry_path.exists():
        df = pd.read_parquet(registry_path)
        required = {"run_type", "slate_id", "created_ts"}
        if not required.issubset(set(map(str, df.columns))):
            missing = sorted(required - set(map(str, df.columns)))
            raise ValueError(
                f"Registry missing required columns {missing}. Re-run upstream variants to populate registry."
            )
        filt = df[(df.get("run_type") == "variants") & (df.get("slate_id") == slate_id)]
        if not filt.empty:
            idx = filt["created_ts"].astype(str).idxmax()
            row = df.loc[idx]
            try:
                primary = row.get("primary_outputs")
                if isinstance(primary, list) and primary:
                    p0 = Path(primary[0])
                    return [p0 if p0.is_absolute() else (out_root / p0)]
            except Exception:
                pass
            run_id = str(row.get("run_id"))
            candidate = (
                out_root
                / "runs"
                / "variants"
                / run_id
                / "artifacts"
                / "variant_catalog.parquet"
            )
            if candidate.exists():
                return [candidate]
    raise FileNotFoundError(
        "No variant catalog found for slate_id="
        f"{slate_id}. Provide --input/--inputs or --from-run."
    )


def _schema_version(schemas_root: Path | None, name: str) -> str:
    schema = load_schema((schemas_root or SCHEMAS_ROOT) / f"{name}.schema.yaml")
    return str(schema.get("version", "0.0.0"))


def _sanity_check_entrant(entry: Mapping[str, Any]) -> None:
    players = list(entry.get("players") or [])
    if len(players) != 8:
        raise ValueError(
            f"Invalid field entrant: expected 8 players, got {len(players)}"
        )
    # If export CSV preview present, ensure it covers 8 slots (order-only check)
    row = str(entry.get("export_csv_row") or "")
    if row:
        parts = [p.strip() for p in row.split(",") if p.strip()]
        if len(parts) != 8:
            raise ValueError("Invalid export_csv_row: expected 8 slot tokens")


def _build_field_df(run_id: str, entrants: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, e in enumerate(entrants, start=1):
        _sanity_check_entrant(e)
        origin = str(e.get("origin") or "variant")
        if origin not in ("variant", "optimizer", "external"):
            origin = "external"
        row: dict[str, Any] = {
            "run_id": run_id,
            "entrant_id": i,
            "origin": origin,
            "players": list(e.get("players") or []),
            "export_csv_row": str(e.get("export_csv_row") or ""),
            "weight": float(e.get("weight", 1.0)),
        }
        if "variant_id" in e:
            row["variant_id"] = str(e["variant_id"])  # optional by schema
        if "lineup_id" in e:
            row["lineup_id"] = str(e["lineup_id"])  # optional by schema
        rows.append(row)
    return pd.DataFrame(rows)


def _build_metrics_df(run_id: str, field_df: pd.DataFrame) -> pd.DataFrame:
    # Per-player exposure rates
    total = int(len(field_df))
    counts: dict[str, int] = {}
    for players in field_df["players"]:
        for p in players:
            counts[str(p)] = counts.get(str(p), 0) + 1
    per_player = (
        [
            {"dk_player_id": pid, "rate": (c / total if total > 0 else 0.0)}
            for pid, c in sorted(counts.items())
        ]
        if counts
        else []
    )
    # Duplication risk: max identical lineup count / total
    from collections import Counter

    lineup_keys = [tuple(sorted(map(str, players))) for players in field_df["players"]]
    dup_counts = Counter(lineup_keys)
    duplication_risk = (max(dup_counts.values()) / total) if total > 0 else 0.0
    row = {
        "run_id": run_id,
        "coverage": {"per_player": per_player},
        "duplication_risk": float(duplication_risk),
    }
    return pd.DataFrame([row])


def run_adapter(
    *,
    slate_id: str,
    config_path: Path | None,
    config_kv: Sequence[str] | None,
    seed: int,
    out_root: Path,
    tag: str | None = None,
    input_path: Path | None = None,
    input_paths: Sequence[Path] | None = None,
    from_run: str | None = None,
    schemas_root: Path | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    created_ts = _utc_now_iso()
    out_root_eff = out_root

    # Resolve inputs
    catalogs = _find_input_variant_catalog(
        out_root=out_root_eff,
        slate_id=slate_id,
        explicit_input=input_path,
        from_run=from_run,
        inputs=input_paths,
    )
    cat_dfs = [pd.read_parquet(p) for p in catalogs]
    catalog_df = (
        pd.concat(cat_dfs, ignore_index=True) if len(cat_dfs) > 1 else cat_dfs[0]
    )

    # Build inputs list for manifest and hashes for run_id
    schemas_root = schemas_root or SCHEMAS_ROOT
    manifest_schema = load_schema(schemas_root / "manifest.schema.yaml")

    inputs_list: list[dict[str, Any]] = []
    cat_shas: list[str] = []
    for p in catalogs:
        sha = _sha256_of_path(p)
        cat_shas.append(sha)
        inputs_list.append({"path": str(p), "content_sha256": sha, "role": "variants"})

    cfg = load_config(config_path, config_kv)
    cfg_knobs = map_config_to_knobs(cfg)
    cfg_sha = hashlib.sha256(
        json.dumps(cfg_knobs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if config_path:
        inputs_list.append(
            {
                "path": str(config_path),
                "content_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
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

    # Deterministic run_id: timestamp + short hash over inputs + cfg + seed
    ts = datetime.now(timezone.utc)
    run_id_core = ts.strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(
        json.dumps(
            {"inputs": cat_shas, "cfg": cfg_sha, "seed": int(seed)}, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()[:8]
    run_id = f"{run_id_core}_{short_hash}"

    # Execute sampler implementation
    sampler = _load_sampler()
    if (
        sampler.__module__ == "field_sampler.engine"
        and sampler.__name__ == "run_sampler"
    ):
        projections_path = cfg.get("projections_csv") or cfg.get("projections_path")
        if not projections_path:
            raise ValueError(
                "projections_csv required in config when using default sampler"
            )
        projections_df = pd.read_csv(Path(projections_path))
        cfg_knobs["variant_catalog"] = catalog_df
        res = sampler(projections_df, cfg_knobs, int(seed))
    else:
        res = sampler(catalog_df, cfg_knobs, int(seed))
    if isinstance(res, tuple) and len(res) >= 1:
        entrants_obj = res[0]
        telemetry = dict(res[1]) if len(res) > 1 and isinstance(res[1], Mapping) else {}
    else:
        entrants_obj = res
        telemetry = {}

    # Normalize entrants into list[dict]
    try:
        import pandas as _pd  # local alias
    except Exception:  # pragma: no cover
        _pd = None
    if _pd is not None and isinstance(entrants_obj, _pd.DataFrame):
        entrants = list(entrants_obj.to_dict(orient="records"))
    elif isinstance(entrants_obj, list):
        entrants = list(entrants_obj)
    else:
        # Attempt to coerce generic iterables of mappings
        entrants = list(entrants_obj)  # type: ignore[arg-type]

    # Build artifacts in-memory and validate (fail-fast) before any writes
    field_df = _build_field_df(run_id, entrants)
    metrics_df = _build_metrics_df(run_id, field_df)
    if validate:
        field_schema = load_schema(schemas_root / "field.schema.yaml")
        metrics_schema = load_schema(schemas_root / "field_metrics.schema.yaml")
        for row in field_df.to_dict(orient="records"):
            validate_obj(field_schema, row, schemas_root=schemas_root)
        for row in metrics_df.to_dict(orient="records"):
            validate_obj(metrics_schema, row, schemas_root=schemas_root)

    # Prepare write locations
    run_dir = out_root_eff / "runs" / "field" / run_id
    artifacts_dir = run_dir / "artifacts"
    ensure_dir(artifacts_dir)
    field_path = artifacts_dir / "field.parquet"
    metrics_path = artifacts_dir / "metrics.parquet"

    # Write artifacts
    write_parquet(field_df, field_path)
    write_parquet(metrics_df, metrics_path)

    # Manifest
    manifest = {
        "schema_version": _schema_version(schemas_root, "manifest"),
        "run_id": run_id,
        "run_type": "field",
        "slate_id": slate_id,
        "created_ts": created_ts,
        "inputs": inputs_list,
        "config": cfg,
        "outputs": [
            {"path": str(field_path), "kind": "field"},
            {"path": str(metrics_path), "kind": "field_metrics"},
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
        "run_type": "field",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(field_path)],
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
        "field_path": str(field_path),
        "metrics_path": str(metrics_path),
        "manifest_path": str(run_dir / "manifest.json"),
        "registry_path": str(registry_path),
        "entrants": int(len(field_df)),
        "variant_catalog_paths": [str(p) for p in catalogs],
        "telemetry": telemetry,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.field_sampler")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--config-kv", nargs="*", help="Inline overrides key=value")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--tag", type=str)
    p.add_argument("--input", type=Path, help="Explicit variant_catalog parquet path")
    p.add_argument(
        "--inputs", nargs="*", type=Path, help="Multiple catalog paths to merge"
    )
    p.add_argument(
        "--from-run",
        type=str,
        help="Variants run_id to source catalog from (run_type=variants)",
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
        input_paths=args.inputs,
        from_run=args.from_run,
        schemas_root=args.schemas_root,
        validate=not args.no_validate,
    )
    if args.verbose:
        known = {
            "field_size",
            "source_mix",
            "sampling_mode",
            "ownership_curve",
            "diversity",
            "team_limits",
            "de-dup",
            "seed",
        }
        cfg = load_config(args.config, args.config_kv)
        unknown = sorted(set(cfg.keys()) - known - {"extras"})
        if unknown:
            print(
                f"[field] Warning: unknown config keys ignored/passthrough: {', '.join(unknown)}",
                file=sys.stderr,
            )
        inputs_msg = ",".join(result.get("variant_catalog_paths", []))
        print(
            f"[field] input={inputs_msg} run_id={result.get('run_id')} entrants={result.get('entrants')}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
