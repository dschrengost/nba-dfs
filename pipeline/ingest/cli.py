from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml

from pipeline.io.files import ensure_dir, write_parquet
from pipeline.io.validate import load_schema, validate_obj


RunTypeForSchema = "ingest"  # constrained by RunTypeEnum in schemas


@dataclass(frozen=True)
class MappingSpec:
    name: str
    header_map: Dict[str, str]
    # set of headers in source to preserve order in lineage
    source_fields: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _mint_run_id(now: Optional[datetime] = None, seed_material: str = "") -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha1(seed_material.encode("utf-8")).hexdigest()[:8]  # nosec: B303
    return f"{ts}_{short}"


def _load_mapping(path: Path) -> MappingSpec:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    header_map: Dict[str, str] = data.get("map", {}) or data.get("mapping", {}) or {}
    if not isinstance(header_map, dict) or not header_map:
        raise ValueError(f"Mapping file {path} missing 'map' or 'mapping' dict")
    name = data.get("name") or path.stem
    return MappingSpec(name=name, header_map=header_map, source_fields=list(header_map.keys()))


def _coerce_numeric(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    if s.startswith("$"):
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def _coerce_int(val: Any) -> Optional[int]:
    f = _coerce_numeric(val)
    return int(f) if f is not None else None


def _normalize_positions(pos: Any) -> str:
    if pos is None:
        return ""
    s = str(pos).upper().replace(" ", "")
    parts = [p for p in s.split("/") if p]
    return "/".join(parts)


def normalize_projections(
    df: pd.DataFrame,
    mapping: MappingSpec,
    slate_id: str,
    source: str,
    updated_ts: Optional[str],
    content_sha256: str,
) -> pd.DataFrame:
    # Invert mapping: canonical_field -> source_header
    inv = {v: k for k, v in mapping.header_map.items()}
    # Build a working DF with canonical columns
    w: Dict[str, Any] = {}
    # Required canonical columns
    w["dk_player_id"] = df[inv.get("dk_player_id", "dk_player_id")]
    w["name"] = df[inv.get("name", "name")]
    w["team"] = df[inv.get("team", "team")].astype(str).str.upper()
    w["pos"] = df[inv.get("pos", "pos")].map(_normalize_positions)
    w["salary"] = df[inv.get("salary", "salary")].map(_coerce_int)
    w["minutes"] = df.get(inv.get("minutes", "minutes"))
    if w["minutes"] is not None:
        w["minutes"] = w["minutes"].map(_coerce_numeric)
    w["proj_fp"] = df[inv.get("proj_fp", "proj_fp")].map(_coerce_numeric)
    # Optional numeric fields
    if inv.get("ceil_fp") in df.columns:
        w["ceil_fp"] = df[inv["ceil_fp"]].map(_coerce_numeric)
    if inv.get("floor_fp") in df.columns:
        w["floor_fp"] = df[inv["floor_fp"]].map(_coerce_numeric)
    if inv.get("own_proj") in df.columns:
        w["own_proj"] = df[inv["own_proj"]].map(_coerce_numeric)

    out = pd.DataFrame(w)
    out.insert(0, "slate_id", slate_id)
    out.insert(1, "source", source)
    out["updated_ts"] = updated_ts or _utc_now_iso()
    out["lineage"] = [
        {
            "mapping": mapping.header_map,
            "source_fields": mapping.source_fields,
            "content_sha256": content_sha256,
        }
        for _ in range(len(out))
    ]
    return out


def apply_latest_wins_priority(
    df: pd.DataFrame,
    source_precedence: Tuple[str, ...] = ("manual", "primary", "other"),
) -> pd.DataFrame:
    # Sort by updated_ts, then by precedence index
    prec_map = {s: i for i, s in enumerate(source_precedence)}
    work = df.copy()
    work["_prec"] = work["source"].map(lambda s: prec_map.get(str(s), len(prec_map)))
    work.sort_values(["dk_player_id", "updated_ts", "_prec"], ascending=[True, True, False], inplace=True)
    # Keep the last occurrence per dk_player_id (latest/lowest precedence index wins)
    deduped = work.groupby("dk_player_id", as_index=False).tail(1).drop(columns=["_prec"])  # type: ignore[no-any-return]
    return deduped.reset_index(drop=True)


def normalize_players(players_csv: Path, now_iso: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(players_csv)
    now = now_iso or _utc_now_iso()
    # Expect columns: dk_player_id, name, team, pos (e.g., "SF/PF")
    if "pos_eligible" in df.columns:
        pos_lists = df["pos_eligible"].apply(lambda s: [p for p in str(s).split("/") if p])
    else:
        pos_lists = df.get("pos")
        if pos_lists is None:
            pos_lists = pd.Series(["" for _ in range(len(df))])
        pos_lists = pos_lists.apply(lambda s: [p for p in str(s).upper().replace(" ", "").split("/") if p])
    out = pd.DataFrame(
        {
            "dk_player_id": df["dk_player_id"].astype(str),
            "name": df["name"].astype(str),
            "team": df["team"].astype(str).str.upper(),
            "pos_eligible": pos_lists,
            "first_seen_ts": now,
            "last_seen_ts": now,
        }
    )
    return out


def build_manifest(
    *,
    run_id: str,
    slate_id: str,
    inputs: List[Dict[str, Any]],
    outputs: List[Dict[str, Any]],
    tags: List[str],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": "0.2.1",
        "run_id": run_id,
        "run_type": RunTypeForSchema,
        "slate_id": slate_id,
        "created_ts": _utc_now_iso(),
        "inputs": inputs,
        "config": config,
        "outputs": outputs,
        "tags": tags,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="pipeline.ingest", description="Normalize projections + register run (PRP-1)")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--source", required=True, help="projection source tag: manual|primary|other|<name>")
    p.add_argument("--projections", required=True, type=Path)
    p.add_argument("--player-ids", required=True, type=Path)
    p.add_argument("--mapping", required=True, type=Path)
    p.add_argument("--out-root", default=Path("data"), type=Path, help="root folder for outputs (tests can override)")
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--validate", dest="validate", action="store_true", default=True)
    p.add_argument("--no-validate", dest="validate", action="store_false")
    p.add_argument("--schemas-root", type=Path, default=Path("pipeline/schemas"))
    args = p.parse_args(list(argv) if argv is not None else None)

    slate_id: str = args.slate_id
    source: str = args.source
    projections_csv: Path = args.projections
    players_csv: Path = args.player_ids
    mapping_path: Path = args.mapping
    out_root: Path = args.out_root
    tags: List[str] = list(args.tag)
    do_validate: bool = bool(args.validate)
    schemas_root: Path = args.schemas_root

    # Safety rail: do not write to workspace data/runs unless explicit out_root provided
    out_root = out_root.resolve()

    # Load mapping and read inputs
    mapping = _load_mapping(mapping_path)
    proj_sha = _sha256_of_file(projections_csv)
    players_sha = _sha256_of_file(players_csv)

    df_raw = pd.read_csv(projections_csv)
    df_norm = normalize_projections(df_raw, mapping, slate_id=slate_id, source=source, updated_ts=None, content_sha256=proj_sha)
    df_norm = apply_latest_wins_priority(df_norm)

    df_players = normalize_players(players_csv)

    # Mint run_id
    run_id = _mint_run_id(seed_material=f"{slate_id}|{source}|{proj_sha[:12]}")

    # Prepare output paths
    ref_dir = out_root / "reference"
    raw_dir = out_root / "projections" / "raw"
    norm_dir = out_root / "projections" / "normalized"
    registry_dir = out_root / "registry"
    runs_dir = out_root / "runs" / "ingest" / run_id
    manifest_path = runs_dir / "manifest.json"

    # Filenames include slate and source and timestamp
    uploaded_ts = _utc_now_iso()
    raw_out = raw_dir / f"{slate_id}__{source}__{uploaded_ts}.parquet"
    norm_out = norm_dir / f"{slate_id}__{source}__{uploaded_ts}.parquet"
    players_out = ref_dir / "players.parquet"
    runs_registry_out = registry_dir / "runs.parquet"

    # Build manifest
    inputs = [
        {"path": str(players_csv), "content_sha256": players_sha, "role": "players"},
        {"path": str(projections_csv), "content_sha256": proj_sha, "role": "config"},
        {"path": str(mapping_path), "content_sha256": _sha256_of_file(mapping_path), "role": "config"},
    ]
    outputs = [
        {"path": str(players_out), "kind": "players"},
        {"path": str(raw_out), "kind": "projections_raw"},
        {"path": str(norm_out), "kind": "projections_normalized"},
        {"path": str(runs_registry_out), "kind": "runs_registry"},
    ]
    manifest = build_manifest(
        run_id=run_id,
        slate_id=slate_id,
        inputs=inputs,
        outputs=outputs,
        tags=tags,
        config={"source": source, "mapping_name": mapping.name},
    )

    # Validate manifest and a single registry row before any writes
    if do_validate:
        try:
            schema_manifest_path = schemas_root / "manifest.schema.yaml"
            schema_manifest = load_schema(schema_manifest_path)
            validate_obj(schema_manifest, manifest, schemas_root=schemas_root, schema_path=schema_manifest_path)
            reg_row_obj = {
                "run_id": run_id,
                "run_type": RunTypeForSchema,
                "slate_id": slate_id,
                "status": "success",
                "primary_outputs": [str(norm_out)],
                "metrics_path": str(runs_dir / "artifacts" / "metrics.json"),
                "created_ts": _utc_now_iso(),
                "tags": tags,
            }
            schema_registry_path = schemas_root / "runs_registry.schema.yaml"
            schema_registry = load_schema(schema_registry_path)
            validate_obj(schema_registry, reg_row_obj, schemas_root=schemas_root, schema_path=schema_registry_path)
        except Exception as e:  # validation error
            print(f"Validation error: {e}", file=sys.stderr)
            return 1

    # Create dirs only after validation succeeds
    ensure_dir(ref_dir)
    ensure_dir(raw_dir)
    ensure_dir(norm_dir)
    ensure_dir(registry_dir)
    ensure_dir(runs_dir)

    # Write artifacts
    write_parquet(df_players, players_out)
    write_parquet(df_raw, raw_out)
    write_parquet(df_norm, norm_out)

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Append registry (very thin: one row per run)
    reg_row = pd.DataFrame([
        {
            "run_id": run_id,
            "run_type": RunTypeForSchema,
            "slate_id": slate_id,
            "status": "success",
            "primary_outputs": [str(norm_out)],
            "metrics_path": str(runs_dir / "artifacts" / "metrics.json"),
            "created_ts": _utc_now_iso(),
            "tags": tags,
        }
    ])
    # Create or append
    if runs_registry_out.exists():
        existing = pd.read_parquet(runs_registry_out)
        write_parquet(pd.concat([existing, reg_row], ignore_index=True), runs_registry_out)
    else:
        write_parquet(reg_row, runs_registry_out)

    # Preview
    preview_cols = [
        "slate_id",
        "source",
        "dk_player_id",
        "name",
        "team",
        "pos",
        "salary",
        "minutes",
        "proj_fp",
        "updated_ts",
    ]
    print(df_norm[preview_cols].head().to_string(index=False))
    print("\nArtifacts:")
    for pth in [players_out, raw_out, norm_out, manifest_path, runs_registry_out]:
        print(f" - {pth}")

    return 0
