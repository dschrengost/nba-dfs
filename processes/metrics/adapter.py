from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj

# Resolve repo root (two levels up from this file) and schemas root
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "pipeline" / "schemas"


def _utc_now_iso() -> str:
    now = datetime.now(UTC)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


def _sha256_of_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_hash(path: Path) -> str:
    try:
        return _sha256_of_path(path) if path and path.exists() else ""
    except Exception:
        return ""


def _schema_version(schemas_root: Path | None, name: str) -> str:
    schema = load_schema((schemas_root or SCHEMAS_ROOT) / f"{name}.schema.yaml")
    return str(schema.get("version", "0.0.0"))


def _load_sim_manifest(out_root: Path, sim_run_id: str) -> dict[str, Any]:
    manifest_path = out_root / "runs" / "sim" / sim_run_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Sim manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Be lenient: ensure a mapping is returned
    if not isinstance(data, dict):
        raise ValueError(f"Invalid sim manifest format: {manifest_path}")
    # Narrow type for mypy
    return data


def _discover_inputs_from_manifest(m: Mapping[str, Any]) -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    for item in m.get("inputs", []) or []:
        role = str(item.get("role", ""))
        p = Path(str(item.get("path", "")))
        if role in ("field", "variants", "contest_structure"):
            discovered[role] = p
    return discovered


def _contest_entry_fee_from_path(path: Path) -> float:
    # Default aligned with sim adapter's contest parser
    default_fee = 20.0
    if not path.exists():
        return default_fee
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            obj = json.loads(path.read_text(encoding="utf-8"))
            fee = obj.get("entry_fee")
            return float(fee) if fee is not None else default_fee
        if suffix == ".parquet":
            df = pd.read_parquet(path)
            if any(str(c).lower() == "entry_fee" for c in df.columns):
                vals = (
                    pd.to_numeric(
                        df[[c for c in df.columns if str(c).lower() == "entry_fee"][0]],
                        errors="coerce",
                    )
                    .dropna()
                    .unique()
                )
                return float(vals[0]) if len(vals) == 1 else default_fee
            return default_fee
        # CSV or others → default (CSV in sim uses default 20)
        return default_fee
    except Exception:
        return default_fee


def _field_lineup_keys(path: Path) -> list[str]:
    if not path.exists():
        return []
    df = pd.read_parquet(path)
    if "export_csv_row" in df.columns:
        vals = [str(v) for v in df["export_csv_row"].tolist()]
        # Filter empties defensively
        return [v for v in vals if v]
    # Fallback: serialize players tuple if available
    if "players" in df.columns:
        lists = df["players"].tolist()
        keys: list[str] = []
        for x in lists:
            try:
                seq = list(x) if x is not None else []
                seq_sorted = sorted(seq)
                keys.append(",".join(str(s) for s in seq_sorted))
            except Exception:
                continue
        return [v for v in keys if v]
    return []


def _duplication_risk_and_entropy(keys: Sequence[str]) -> tuple[float, float]:
    n = len(keys)
    if n == 0:
        return 0.0, 0.0
    counts: dict[str, int] = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1
    unique = len(counts)
    dup_risk = 1.0 - (unique / float(n))
    # Shannon entropy (bits)
    entropy = 0.0
    for c in counts.values():
        p = c / float(n)
        if p > 0:
            entropy -= p * math.log2(p)
    return float(dup_risk), float(entropy)


def _aggregate_portfolio_metrics(sim_results: pd.DataFrame, entry_fee: float) -> dict[str, float]:
    # Expect columns: prize; compute return per trial as (prize - fee)/fee
    fee = float(entry_fee) if entry_fee and entry_fee > 0 else 20.0
    prize = pd.to_numeric(sim_results.get("prize"), errors="coerce").fillna(0.0)
    returns = (prize - fee) / fee
    roi_mean = float(returns.mean()) if len(returns) else 0.0
    stdev = float(returns.std(ddof=0)) if len(returns) > 1 else 0.0
    sharpe = float(roi_mean / stdev) if stdev > 0 else 0.0
    neg = returns[returns < 0]
    downside = float(neg.std(ddof=0)) if len(neg) > 1 else 0.0
    sortino = float(roi_mean / downside) if downside > 0 else 0.0
    return {"roi_mean": roi_mean, "sharpe": sharpe, "sortino": sortino}


def run_adapter(
    *,
    from_sim_run: str,
    out_root: Path,
    seed: int = 42,
    tag: str | None = None,
    schemas_root: Path | None = None,
    verbose: bool = False,
    deterministic: bool = False,
    fixed_ts: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Compute metrics from an existing sim run. Supports deterministic run IDs and optional validation toggle."""
    schemas_root = schemas_root or SCHEMAS_ROOT
    created_ts = _utc_now_iso()

    if fixed_ts:
        created_ts = fixed_ts

    # Discover sim artifacts
    sim_run_dir = out_root / "runs" / "sim" / from_sim_run
    sim_artifacts = sim_run_dir / "artifacts"
    sim_results_path = sim_artifacts / "sim_results.parquet"
    if not sim_results_path.exists():
        raise FileNotFoundError(f"sim_results not found: {sim_results_path}")
    sim_results_df = pd.read_parquet(sim_results_path)
    sim_manifest = _load_sim_manifest(out_root, from_sim_run)
    slate_id = str(sim_manifest.get("slate_id", "UNKNOWN"))
    inputs = _discover_inputs_from_manifest(sim_manifest)

    # Entry fee from contest (default if absent)
    entry_fee = _contest_entry_fee_from_path(inputs.get("contest_structure", Path("")))

    # Duplication and entropy from field or variants
    lineup_keys: list[str] = []
    if "field" in inputs:
        lineup_keys = _field_lineup_keys(inputs["field"])
    elif "variants" in inputs:
        lineup_keys = _field_lineup_keys(inputs["variants"])
    dup_risk, entropy = _duplication_risk_and_entropy(lineup_keys)

    # Portfolio aggregates from sim results
    portfolio_aggs = _aggregate_portfolio_metrics(sim_results_df, entry_fee)
    portfolio_aggs["duplication_risk"] = dup_risk
    portfolio_aggs["entropy"] = entropy

    # Run ID: deterministic option based on content hash, or timestamped default
    results_sha = _sha256_of_path(sim_results_path)
    if deterministic:
        short_hash = hashlib.sha256(f"{results_sha}|{seed}".encode()).hexdigest()[:8]
        run_id = f"metrics_{short_hash}"
    else:
        now_dt = datetime.fromisoformat(created_ts.replace("Z", "+00:00"))
        run_id_core = now_dt.strftime("%Y%m%d_%H%M%S")
        short_hash = hashlib.sha256(f"{from_sim_run}|{results_sha}|{seed}".encode()).hexdigest()[:8]
        run_id = f"{run_id_core}_{short_hash}"

    # Build output directories
    run_dir = out_root / "runs" / "metrics" / run_id
    artifacts_dir = run_dir / "artifacts"
    ensure_dir(artifacts_dir)

    # Prepare metrics dataframe
    metrics_row = {"run_id": run_id, "aggregates": portfolio_aggs}

    # Validate against metrics schema before write
    metrics_schema = load_schema(schemas_root / "metrics.schema.yaml")
    if validate:
        validate_obj(metrics_schema, metrics_row, schemas_root=schemas_root)
    metrics_df = pd.DataFrame([metrics_row])

    metrics_path = artifacts_dir / "metrics.parquet"
    write_parquet(metrics_df, metrics_path)

    # Manifest
    manifest_schema = load_schema(schemas_root / "manifest.schema.yaml")
    inputs_for_manifest: list[dict[str, Any]] = [
        {
            "path": str(sim_results_path),
            "content_sha256": results_sha,
            "role": "sim_results",
        }
    ]
    if "field" in inputs:
        inputs_for_manifest.append(
            {
                "path": str(inputs["field"]),
                "content_sha256": _safe_hash(inputs["field"]),
                "role": "field",
            }
        )
    if "variants" in inputs:
        inputs_for_manifest.append(
            {
                "path": str(inputs["variants"]),
                "content_sha256": _safe_hash(inputs["variants"]),
                "role": "variants",
            }
        )
    if "contest_structure" in inputs:
        inputs_for_manifest.append(
            {
                "path": str(inputs["contest_structure"]),
                "content_sha256": _safe_hash(inputs["contest_structure"]),
                "role": "contest_structure",
            }
        )

    manifest = {
        "schema_version": _schema_version(schemas_root, "manifest"),
        "run_id": run_id,
        "run_type": "metrics",
        "slate_id": slate_id,
        "created_ts": created_ts,
        "inputs": inputs_for_manifest,
        "config": {"seed": int(seed), "from_sim_run": str(from_sim_run)},
        "outputs": [
            {"path": str(metrics_path), "kind": "metrics"},
        ],
        "tags": [tag] if tag else [],
    }
    if validate:
        validate_obj(manifest_schema, manifest, schemas_root=schemas_root)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Registry append
    registry_path = out_root / "registry" / "runs.parquet"
    ensure_dir(registry_path.parent)
    reg_row = {
        "run_id": run_id,
        "run_type": "metrics",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(metrics_path)],
        "metrics_path": str(metrics_path),
        "created_ts": created_ts,
        "tags": [tag] if tag else [],
    }
    runs_registry_schema = load_schema(schemas_root / "runs_registry.schema.yaml")
    if validate:
        validate_obj(runs_registry_schema, reg_row, schemas_root=schemas_root)
    if registry_path.exists():
        existing = pd.read_parquet(registry_path)
        reg_df = pd.concat([existing, pd.DataFrame([reg_row])], ignore_index=True)
    else:
        reg_df = pd.DataFrame([reg_row])
    write_parquet(reg_df, registry_path)

    if verbose:
        print(f"[metrics] run_id: {run_id}")
        print(f"[metrics] sim_results: {sim_results_path}")
        print(f"[metrics] entry_fee: {entry_fee}")
        print(f"[metrics] dup_risk: {dup_risk:.4f}, entropy(bits): {entropy:.4f}")
        print(f"[metrics] roi_mean: {portfolio_aggs['roi_mean']:.6f}")
        print(f"[metrics] sharpe: {portfolio_aggs['sharpe']:.6f}")
        print(f"[metrics] sortino: {portfolio_aggs['sortino']:.6f}")

    return {
        "run_id": run_id,
        "metrics_path": str(metrics_path),
        "manifest_path": str(run_dir / "manifest.json"),
        "registry_path": str(registry_path),
        "entry_fee": float(entry_fee),
        "duplication_risk": float(dup_risk),
        "entropy_bits": float(entropy),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.metrics")
    p.add_argument("--from-sim", required=True, dest="from_sim_run")
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tag", type=str)
    p.add_argument("--schemas-root", type=Path)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--deterministic", action="store_true")
    p.add_argument(
        "--fixed-ts",
        type=str,
        help="Override created_ts (ISO8601, e.g., 2025-09-06T12:34:56.789Z)",
    )
    p.add_argument("--no-validate", dest="validate", action="store_false")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    run_adapter(
        from_sim_run=str(ns.from_sim_run),
        out_root=ns.out_root,
        seed=int(ns.seed),
        tag=ns.tag,
        schemas_root=ns.schemas_root,
        verbose=bool(ns.verbose),
        deterministic=bool(ns.deterministic),
        fixed_ts=str(ns.fixed_ts) if ns.fixed_ts else None,
        validate=bool(ns.validate),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
