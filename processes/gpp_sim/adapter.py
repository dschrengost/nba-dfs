from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj

# Resolve repo root (two levels up from this file) and schemas root
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "pipeline" / "schemas"


RunSimFn = Callable[[pd.DataFrame, dict[str, Any], dict[str, Any], int], Any]


DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


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


def load_config(config_path: Path | None, inline_kv: Sequence[str] | None = None) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if config_path:
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() in (".yaml", ".yml"):
            import yaml  # lazy

            try:
                cfg = dict(yaml.safe_load(text) or {})
            except Exception as e:  # pragma: no cover
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
    """Translate user config to simulator knobs and preserve extras.

    Known keys:
    - num_trials, projection_model, boom_bust, dup_penalty, late_swap,
      min_cash_prob, seed
    Unknown keys are preserved under `extras`.
    """
    c: dict[str, Any] = {}
    for key in (
        "num_trials",
        "projection_model",
        "boom_bust",
        "dup_penalty",
        "late_swap",
        "min_cash_prob",
        "seed",
    ):
        if key in config:
            c[key] = config[key]
    # Preserve extras
    for k, v in config.items():
        if k not in c:
            c.setdefault("extras", {})[k] = v
    return c


def export_csv_row_preview(
    players: Sequence[str], dk_positions_filled: Sequence[Mapping[str, Any]]
) -> str:
    """Build DK CSV preview string robustly.

    Uses canonical order PG,SG,SF,PF,C,G,F,UTIL with tokens "<slot> <player_id>".
    Handles mismatched lengths by mapping up to the shorter length.
    """
    slot_to_player: dict[str, str] = {}
    n = min(len(players), len(dk_positions_filled))
    for idx in range(n):
        slot_item = dk_positions_filled[idx]
        getter = getattr(slot_item, "get", None)
        slot_val = getter("slot") if callable(getter) else None
        slot = str(slot_val or "")
        slot_to_player[slot] = str(players[idx])
    cols: list[str] = []
    for slot_label in DK_SLOTS_ORDER:
        pid = slot_to_player.get(slot_label, "")
        cols.append(f"{slot_label} {pid}".strip())
    return ",".join(cols)


def _dk_preview_to_upload_row(preview: str) -> str:
    """Convert preview tokens "PG p1,SG p2,..." to DK upload row "p1,p2,..."."""
    parts = [p.strip() for p in preview.split(",")]
    ids = [p.split(" ", 1)[-1] if " " in p else "" for p in parts]
    return ",".join(ids)


def _schema_version(schemas_root: Path | None, name: str) -> str:
    schema = load_schema((schemas_root or SCHEMAS_ROOT) / f"{name}.schema.yaml")
    return str(schema.get("version", "0.0.0"))


def _load_sim_impl() -> RunSimFn:
    override = os.environ.get("GPP_SIM_IMPL")
    if override:
        mod_name, _, fn_name = override.partition(":")
        mod = __import__(mod_name, fromlist=[fn_name or "run_sim"])
        fn = getattr(mod, fn_name or "run_sim")
        return cast(RunSimFn, fn)
    # No built-in default; tests will monkeypatch this function.
    raise ImportError(
        "No GPP simulator implementation available. Provide GPP_SIM_IMPL or "
        "monkeypatch _load_sim_impl in tests."
    )


def _validate_field_df(df: pd.DataFrame) -> None:
    # Basic guards: 8 players per lineup
    if "players" not in df.columns:
        raise ValueError("Field missing 'players' column")
    for i, players in enumerate(df["players"].tolist()):
        # Accept any non-string sequence-like with len==8
        ok_len = False
        if isinstance(players, list) or isinstance(players, tuple):
            ok_len = len(players) == 8
        else:
            if hasattr(players, "__len__") and not (
                isinstance(players, str) or isinstance(players, bytes)
            ):
                try:
                    ok_len = len(players) == 8
                except Exception:
                    ok_len = False
        if not ok_len:
            raise ValueError(f"Invalid field row {i}: expected 8 players")
    # Optional salary guard if present
    if "total_salary" in df.columns:
        if pd.to_numeric(df["total_salary"], errors="coerce").max() > 50000:
            raise ValueError("Field row exceeds DK salary cap 50000")


def _contest_from_path(path: Path) -> dict[str, Any]:
    """Load contest structure from csv|parquet|json to schema shape.

    CSV expected columns: rank_start, rank_end, prize
    Missing contest metadata is filled with defaults; field_size inferred from
    payout ranges.
    """
    suffix = path.suffix.lower()
    if suffix == ".json":
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if suffix == ".parquet":
        pdf = pd.read_parquet(path)
    else:
        # Manual parse for CSV to handle unquoted thousands separators cleanly
        with open(path, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            rows: list[dict[str, str]] = []
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split(",", 2)
                if len(parts) < 3:
                    continue
                rows.append(
                    {
                        header[0]: parts[0].strip(),
                        header[1]: parts[1].strip(),
                        "prize": parts[2].strip(),
                    }
                )
        pdf = pd.DataFrame(rows)
    # normalize columns
    cols = {c.lower(): c for c in map(str, pdf.columns)}

    def col(name: str) -> str:
        for k, v in cols.items():
            if k == name.lower():
                return v
        return name

    payout_curve: list[dict[str, Any]] = []
    for _, row in pdf.iterrows():

        def _parse_place(val: str) -> tuple[int, int]:
            s = str(val).strip()
            parts = [p.strip() for p in s.split("-")]
            try:
                a = int(parts[0])
                b = int(parts[-1])
            except Exception:
                a = b = int(parts[0]) if parts and parts[0].isdigit() else 0
            return a, b

        if col("rank_start") in pdf.columns and col("rank_end") in pdf.columns:
            a = int(str(row[col("rank_start")]).strip())
            b = int(str(row[col("rank_end")]).strip())
        else:
            a, b = _parse_place(row[col("place")])

        raw_prize = str(row[col("prize")] if col("prize") in pdf.columns else row[col("payout")])
        prize = float(raw_prize.replace(",", "").replace("$", "").strip())
        payout_curve.append({"rank_start": a, "rank_end": b, "prize": prize})
    # Defaults
    field_size = sum(int(p["rank_end"]) - int(p["rank_start"]) + 1 for p in payout_curve)
    contest = {
        "contest_id": f"TEST_{path.stem}",
        "name": path.stem,
        "field_size": int(field_size),
        "payout_curve": payout_curve,
        "entry_fee": float(20),
        "rake": 0.15,
        "site": "DK",
    }
    return contest


def _validate_contest_structure(c: Mapping[str, Any]) -> None:
    # Contiguous, non-overlapping, exhaustive coverage
    curve = list(c.get("payout_curve") or [])
    field_size = int(c.get("field_size") or 0)
    if field_size <= 0:
        raise ValueError("Contest field_size must be > 0")
    covered: set[int] = set()
    for p in curve:
        a = int(p.get("rank_start", 0))
        b = int(p.get("rank_end", 0))
        if a < 1 or b < a:
            raise ValueError("Invalid payout range")
        for r in range(a, b + 1):
            if r in covered:
                raise ValueError("Overlapping payout ranges")
            covered.add(r)
    if covered != set(range(1, field_size + 1)):
        raise ValueError("Payout ranges must exactly cover 1..field_size")
    rake = float(c.get("rake", 0.0))
    if not (0 <= rake < 1):
        raise ValueError("Contest rake must be in [0,1)")
    if float(c.get("entry_fee", 0.0)) < 0:
        raise ValueError("Contest entry_fee must be >= 0")


def _find_field_input(
    *,
    out_root: Path,
    explicit_field: Path | None = None,
    from_field_run: str | None = None,
    variants_path: Path | None = None,
) -> tuple[Path, str]:
    # Returns (path, role)
    if explicit_field is not None:
        return explicit_field, "field"
    if from_field_run:
        candidate = out_root / "runs" / "field" / from_field_run / "artifacts" / "field.parquet"
        if candidate.exists():
            return candidate, "field"
        raise FileNotFoundError(f"--from-field-run provided but not found: {candidate}")
    if variants_path is not None:
        return variants_path, "variants"
    raise FileNotFoundError(
        "No field input provided. Use --field, --from-field-run, or --variants."
    )


def _find_contest_input(
    *, explicit_contest: Path | None = None, from_contest_dir: Path | None = None
) -> Path:
    if explicit_contest is not None:
        return explicit_contest
    if from_contest_dir is not None:
        names = [
            "contest_structure.csv",
            "contest.csv",
            "contest.json",
            "contest.parquet",
        ]
        for n in names:
            p = from_contest_dir / n
            if p.exists():
                return p
        raise FileNotFoundError(f"No contest file found under {from_contest_dir}")
    raise FileNotFoundError("No contest input provided. Use --contest or --from-contest.")


def _build_sim_results_df(run_id: str, rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "run_id": run_id,
            "world_id": int(r.get("world_id", 0)),
            "entrant_id": r.get("entrant_id"),
            "score": float(r.get("score", 0.0)),
            "rank": int(r.get("rank", 1)),
            "prize": float(r.get("prize", 0.0)),
        }
        if "components" in r:
            row["components"] = r["components"]
        if "seed" in r:
            row["seed"] = int(r["seed"])  # optional
        out.append(row)
    return pd.DataFrame(out)


def _build_sim_metrics_df(run_id: str, aggregates: Mapping[str, Any]) -> pd.DataFrame:
    ag = {
        "ev_mean": float(aggregates.get("ev_mean", 0.0)),
        "roi_mean": float(aggregates.get("roi_mean", 0.0)),
    }
    # Optional extras
    for opt in ("sharpe", "sortino"):
        if opt in aggregates:
            ag[opt] = float(aggregates[opt])
    return pd.DataFrame([{"run_id": run_id, "aggregates": ag}])


def _execute_sim(
    field_df: pd.DataFrame, contest: dict[str, Any], knobs: dict[str, Any], seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    run_sim = _load_sim_impl()
    res = run_sim(field_df, contest, knobs, seed)
    telemetry: dict[str, Any] = {}
    if isinstance(res, tuple) and len(res) >= 2:
        rows_raw = res[0]
        aggs = res[1]
        if len(res) > 2 and isinstance(res[2], Mapping):
            telemetry = dict(res[2])
    else:
        rows_raw = cast(Sequence[Mapping[str, Any]], res)
        aggs = {"ev_mean": 0.0, "roi_mean": 0.0}
    results_df = (
        rows_raw
        if isinstance(rows_raw, pd.DataFrame)
        else _build_sim_results_df("RID_PLACEHOLDER", rows_raw)
    )
    # We temporarily build with placeholder run_id; caller will set actual run_id below.
    metrics_df = (
        aggs
        if isinstance(aggs, pd.DataFrame)
        else _build_sim_metrics_df("RID_PLACEHOLDER", cast(Mapping[str, Any], aggs))
    )
    return results_df, metrics_df, telemetry


def run_adapter(
    *,
    slate_id: str,
    config_path: Path | None,
    config_kv: Sequence[str] | None,
    seed: int,
    out_root: Path,
    tag: str | None,
    field_path: Path | None,
    from_field_run: str | None,
    variants_path: Path | None,
    contest_path: Path | None,
    from_contest_dir: Path | None,
    schemas_root: Path | None = None,
    validate: bool = True,
    verbose: bool = False,
    export_dk_csv: Path | None = None,
) -> dict[str, Any]:
    schemas_root = schemas_root or SCHEMAS_ROOT
    # Mint timestamp once and reuse for created_ts and run_id core
    now = datetime.now(UTC)
    ms = int(now.microsecond / 1000)
    created_ts = f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"

    # Resolve inputs
    field_input, field_role = _find_field_input(
        out_root=out_root,
        explicit_field=field_path,
        from_field_run=from_field_run,
        variants_path=variants_path,
    )
    contest_input = _find_contest_input(
        explicit_contest=contest_path, from_contest_dir=from_contest_dir
    )
    if verbose:
        print(f"[sim] field: {field_input} (role={field_role})", file=sys.stderr)
        print(f"[sim] contest: {contest_input}", file=sys.stderr)
        print(f"[sim] schemas_root: {schemas_root}", file=sys.stderr)

    # Load/validate inputs
    if field_role == "field":
        field_df = pd.read_parquet(field_input)
        _validate_field_df(field_df)
    else:  # variants → field
        catalog = pd.read_parquet(field_input)
        rows: list[dict[str, Any]] = []
        for i, v in enumerate(catalog.to_dict(orient="records"), start=1):
            _players_val = v.get("players")
            players = list(_players_val) if _players_val is not None else []
            row = {
                "run_id": str(v.get("run_id", "")),
                "entrant_id": i,
                "origin": "variant",
                "variant_id": str(v.get("variant_id", f"V{i}")),
                "players": players,
                "export_csv_row": export_csv_row_preview(
                    players, list(v.get("dk_positions_filled") or [])
                ),
                "weight": 1.0,
            }
            if verbose and not v.get("dk_positions_filled"):
                print(
                    "[sim] variants row missing dk_positions_filled; "
                    "export preview will have blanks",
                    file=sys.stderr,
                )
            rows.append(row)
        field_df = pd.DataFrame(rows)
        _validate_field_df(field_df)

    contest = _contest_from_path(contest_input)

    # Map config → knobs
    cfg = load_config(config_path, config_kv)
    knobs = map_config_to_knobs(cfg)
    knobs["seed"] = int(seed)
    if verbose:
        known = {
            "num_trials",
            "projection_model",
            "boom_bust",
            "dup_penalty",
            "late_swap",
            "min_cash_prob",
            "seed",
        }
        unknown = [k for k in cfg.keys() if k not in known]
        if unknown:
            print(
                f"[sim] unknown config keys preserved: {sorted(unknown)}",
                file=sys.stderr,
            )

    # Compute input SHAs for determinism and manifest
    inputs_list: list[dict[str, Any]] = []
    field_sha = _sha256_of_path(field_input)
    inputs_list.append({"path": str(field_input), "content_sha256": field_sha, "role": field_role})
    contest_sha = _sha256_of_path(contest_input)
    inputs_list.append(
        {
            "path": str(contest_input),
            "content_sha256": contest_sha,
            "role": "contest_structure",
        }
    )
    cfg_blob = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode("utf-8")
    cfg_sha = hashlib.sha256(cfg_blob).hexdigest()
    if config_path:
        inputs_list.append({"path": str(config_path), "content_sha256": cfg_sha, "role": "config"})
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
                    json.dumps(kv_parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "role": "config",
            }
        )

    # Deterministic run_id
    run_id_core = now.strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(f"{field_sha}|{contest_sha}|{cfg_sha}|{seed}".encode()).hexdigest()[
        :8
    ]
    run_id = f"{run_id_core}_{short_hash}"

    # Execute simulation
    results_df, metrics_df, telemetry = _execute_sim(field_df, contest, knobs, seed)
    # Ensure run_id column exists for all rows
    results_df = results_df.copy()
    results_df["run_id"] = run_id
    metrics_df = metrics_df.copy()
    metrics_df["run_id"] = run_id

    if verbose:
        print(f"[sim] run_id={run_id}", file=sys.stderr)

    # Validate rows before any writes
    if validate:
        sim_results_schema = load_schema(schemas_root / "sim_results.schema.yaml")
        sim_metrics_schema = load_schema(schemas_root / "sim_metrics.schema.yaml")
        for row in results_df.to_dict(orient="records"):
            validate_obj(sim_results_schema, row, schemas_root=schemas_root)
        for row in metrics_df.to_dict(orient="records"):
            validate_obj(sim_metrics_schema, row, schemas_root=schemas_root)
        # Contest structure + manifest validation
        contest_schema = load_schema(schemas_root / "contest_structure.schema.yaml")
        validate_obj(contest_schema, contest, schemas_root=schemas_root)
        _validate_contest_structure(contest)

    # Write artifacts
    run_dir = out_root / "runs" / "sim" / run_id
    artifacts_dir = run_dir / "artifacts"
    ensure_dir(artifacts_dir)
    results_path = artifacts_dir / "sim_results.parquet"
    metrics_path = artifacts_dir / "metrics.parquet"
    write_parquet(results_df, results_path)
    write_parquet(metrics_df, metrics_path)

    # Optional DK CSV export from field preview
    if export_dk_csv is not None:
        ensure_dir(Path(export_dk_csv).parent)
        with open(export_dk_csv, "w", encoding="utf-8") as f:
            f.write(",".join(DK_SLOTS_ORDER) + "\n")
            for _, row in field_df.head(50).iterrows():
                preview = str(row.get("export_csv_row", ""))
                if preview:
                    f.write(_dk_preview_to_upload_row(preview) + "\n")

    # Manifest
    manifest_schema = load_schema(schemas_root / "manifest.schema.yaml")
    manifest = {
        "schema_version": _schema_version(schemas_root, "manifest"),
        "run_id": run_id,
        "run_type": "sim",
        "slate_id": slate_id,
        "created_ts": created_ts,
        "inputs": inputs_list,
        "config": cfg,
        "outputs": [
            {"path": str(results_path), "kind": "sim_results"},
            {"path": str(metrics_path), "kind": "sim_metrics"},
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
        "run_type": "sim",
        "slate_id": slate_id,
        "status": "success",
        "primary_outputs": [str(results_path)],
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
        "sim_results_path": str(results_path),
        "metrics_path": str(metrics_path),
        "manifest_path": str(run_dir / "manifest.json"),
        "registry_path": str(registry_path),
        "telemetry": telemetry,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.gpp_sim")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--config-kv", nargs="*", help="Inline overrides key=value")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--tag", type=str)
    # Discovery: field
    p.add_argument("--field", type=Path, help="Explicit field parquet path")
    p.add_argument("--from-field-run", type=str, help="Field run_id under runs/field/")
    p.add_argument("--variants", type=Path, help="Variant catalog parquet (fallback)")
    # Discovery: contest
    p.add_argument("--contest", type=Path, help="Contest structure file (csv|parquet|json)")
    p.add_argument("--from-contest", type=Path, help="Directory to search for contest file")
    # Infra
    p.add_argument("--schemas-root", type=Path)
    p.add_argument(
        "--validate",
        dest="validate",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--export-dk-csv", type=Path)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    p = _build_parser()
    ns = p.parse_args(argv)
    try:
        run_adapter(
            slate_id=str(ns.slate_id),
            config_path=ns.config,
            config_kv=ns.config_kv,
            seed=int(ns.seed),
            out_root=ns.out_root,
            tag=ns.tag,
            field_path=ns.field,
            from_field_run=ns.from_field_run,
            variants_path=ns.variants,
            contest_path=ns.contest,
            from_contest_dir=ns.from_contest,
            schemas_root=ns.schemas_root,
            validate=bool(ns.validate),
            verbose=bool(ns.verbose),
            export_dk_csv=ns.export_dk_csv,
        )
    except Exception as e:  # pragma: no cover - error path
        print(f"[sim] error: {e}", file=sys.stderr)
        return 1
    return 0
