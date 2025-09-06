from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

# Stage adapters
from pipeline import ingest as ingest_pkg
from processes.optimizer import adapter as opt
from processes.variants import adapter as var
from processes.field_sampler import adapter as fld
from processes.gpp_sim import adapter as sim


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT_DEFAULT = REPO_ROOT / "pipeline" / "schemas"


def _utc_now_iso() -> str:
    now = datetime.now(timezone.utc)
    ms = int(now.microsecond / 1000)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{ms:03d}Z"


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


def _load_config(path: Path | None, kv: Sequence[str] | None) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if path is not None:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            import yaml  # lazy

            cfg = dict(yaml.safe_load(text) or {})
        else:
            cfg = dict(json.loads(text))
    if kv:
        for item in kv:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            cfg[k.strip()] = _coerce_scalar(v.strip())
    return cfg


def _mint_bundle_id(seed_material: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:8]
    return f"{ts}_{short}"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


@dataclass
class StageResult:
    name: str
    run_id: str
    manifest_path: Path
    primary_output: str | None


def _write_stage_config(temp_dir: Path, stage: str, cfg: Mapping[str, Any]) -> Path:
    path = temp_dir / f"{stage}.config.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return path


def run_bundle(
    *,
    slate_id: str,
    config_path: Path,
    config_kv: Sequence[str] | None,
    out_root: Path,
    schemas_root: Path | None,
    validate: bool,
    dry_run: bool,
    verbose: bool,
) -> dict[str, Any]:
    cfg = _load_config(config_path, config_kv)
    seeds = {
        "optimizer": int(cfg.get("seeds", {}).get("optimizer", 42)),
        "variants": int(cfg.get("seeds", {}).get("variants", 42)),
        "field": int(cfg.get("seeds", {}).get("field", 42)),
        "sim": int(cfg.get("seeds", {}).get("sim", 42)),
    }
    stages_cfg: dict[str, Mapping[str, Any]] = {
        "ingest": dict(cfg.get("ingest", {})),
        "optimizer": dict(cfg.get("optimizer", {})),
        "variants": dict(cfg.get("variants", {})),
        "field": dict(cfg.get("field", {})),
        "sim": dict(cfg.get("sim", {})),
    }

    plan = [
        f"ingest: source={stages_cfg['ingest'].get('source','?')} projections={stages_cfg['ingest'].get('projections','?')}",
        "optimizer: from=ingest normalized",
        "variants: from=optimizer lineups",
        "field: from=variants catalog",
        "sim: from=field (or variants)",
    ]
    if verbose or dry_run:
        print("[orchestrator] plan:", file=sys.stderr)
        for step in plan:
            print(f"  - {step}", file=sys.stderr)

    if dry_run:
        return {"bundle_id": "DRY_RUN", "plan": plan}

    out_root = out_root.resolve()
    schemas_root = (schemas_root or SCHEMAS_ROOT_DEFAULT).resolve()

    # Prepare orchestrator run dir
    bundle_seed_material = json.dumps(
        {
            "slate_id": slate_id,
            "seeds": seeds,
            "optimizer_cfg": stages_cfg.get("optimizer"),
            "variants_cfg": stages_cfg.get("variants"),
            "field_cfg": stages_cfg.get("field"),
            "sim_cfg": stages_cfg.get("sim"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    bundle_id = _mint_bundle_id(bundle_seed_material)
    bundle_dir = out_root / "runs" / "orchestrator" / bundle_id
    _ensure_dir(bundle_dir)

    stage_results: list[StageResult] = []

    # 1) Ingest
    ing = stages_cfg["ingest"]
    ingest_args = [
        "--slate-id",
        str(slate_id),
        "--source",
        str(ing.get("source", "manual")),
        "--projections",
        str(ing.get("projections")),
        "--player-ids",
        str(ing.get("player_ids")),
        "--mapping",
        str(ing.get("mapping")),
        "--out-root",
        str(out_root),
        "--schemas-root",
        str(schemas_root),
    ]
    if not validate:
        ingest_args.append("--no-validate")
    rc = ingest_pkg.cli.main(ingest_args)
    if rc != 0:
        raise RuntimeError(f"ingest stage failed (exit={rc})")
    # Discover ingest run in registry
    registry_path = out_root / "registry" / "runs.parquet"
    if not registry_path.exists():
        raise FileNotFoundError("Registry not found after ingest stage")
    reg = pd.read_parquet(registry_path)
    mask = (reg.get("run_type") == "ingest") & (reg.get("slate_id") == slate_id)
    if not mask.any():
        raise RuntimeError("No ingest run discovered in registry")
    row = reg.loc[mask]["created_ts"].astype(str)
    idx = row.idxmax()
    ingest_run = str(reg.loc[idx, "run_id"])  # type: ignore[index]
    ingest_manifest = out_root / "runs" / "ingest" / ingest_run / "manifest.json"
    stage_results.append(
        StageResult(
            name="ingest",
            run_id=ingest_run,
            manifest_path=ingest_manifest,
            primary_output=str(reg.loc[idx, "primary_outputs"][0]) if isinstance(reg.loc[idx, "primary_outputs"], list) and reg.loc[idx, "primary_outputs"] else None,  # type: ignore[index]
        )
    )

    # 2) Optimizer
    opt_cfg = dict(stages_cfg["optimizer"])
    site = str(opt_cfg.pop("site", "DK"))
    engine = str(opt_cfg.pop("engine", "cbc"))
    opt_cfg_path = _write_stage_config(bundle_dir, "optimizer", opt_cfg)
    opt_res = opt.run_adapter(
        slate_id=slate_id,
        site=site,
        config_path=opt_cfg_path,
        config_kv=None,
        engine=engine,
        seed=int(seeds["optimizer"]),
        out_root=out_root,
        tag=f"bundle:{bundle_id}",
        in_root=out_root,
        input_path=None,
        schemas_root=schemas_root,
    )
    stage_results.append(
        StageResult(
            name="optimizer",
            run_id=str(opt_res.get("run_id")),
            manifest_path=Path(str(opt_res.get("manifest_path"))),
            primary_output=str(opt_res.get("lineups_path")),
        )
    )

    # 3) Variants
    var_cfg = dict(stages_cfg["variants"])
    var_cfg_path = _write_stage_config(bundle_dir, "variants", var_cfg)
    var_res = var.run_adapter(
        slate_id=slate_id,
        config_path=var_cfg_path,
        config_kv=None,
        seed=int(seeds["variants"]),
        out_root=out_root,
        tag=f"bundle:{bundle_id}",
        input_path=None,
        from_run=str(opt_res.get("run_id")),
        schemas_root=schemas_root,
        validate=validate,
    )
    stage_results.append(
        StageResult(
            name="variants",
            run_id=str(var_res.get("run_id")),
            manifest_path=Path(str(var_res.get("manifest_path"))),
            primary_output=str(var_res.get("catalog_path")),
        )
    )

    # 4) Field Sampler
    fld_cfg = dict(stages_cfg["field"])
    fld_cfg_path = _write_stage_config(bundle_dir, "field", fld_cfg)
    fld_res = fld.run_adapter(
        slate_id=slate_id,
        config_path=fld_cfg_path,
        config_kv=None,
        seed=int(seeds["field"]),
        out_root=out_root,
        tag=f"bundle:{bundle_id}",
        input_path=None,
        input_paths=None,
        from_run=str(var_res.get("run_id")),
        schemas_root=schemas_root,
        validate=validate,
    )
    stage_results.append(
        StageResult(
            name="field",
            run_id=str(fld_res.get("run_id")),
            manifest_path=Path(str(fld_res.get("manifest_path"))),
            primary_output=str(fld_res.get("field_path")),
        )
    )

    # 5) GPP Sim
    sim_cfg = dict(stages_cfg["sim"])
    contest_obj = sim_cfg.pop("contest", None)
    contest_path = sim_cfg.pop("contest_path", None)
    if contest_obj is not None and contest_path is None:
        # Ensure required fields present for schema validation
        if "contest_id" not in contest_obj:
            contest_obj["contest_id"] = f"TEST_{bundle_id}"
        if "name" not in contest_obj:
            contest_obj["name"] = "Test Contest"
        contest_path = bundle_dir / "contest.json"
        Path(contest_path).write_text(json.dumps(contest_obj, indent=2), encoding="utf-8")
    sim_cfg_path = _write_stage_config(bundle_dir, "sim", sim_cfg)
    sim_res = sim.run_adapter(
        slate_id=slate_id,
        config_path=sim_cfg_path,
        config_kv=None,
        seed=int(seeds["sim"]),
        out_root=out_root,
        tag=f"bundle:{bundle_id}",
        field_path=None,
        from_field_run=str(fld_res.get("run_id")),
        variants_path=None,
        contest_path=Path(contest_path) if contest_path else None,
        from_contest_dir=None,
        schemas_root=schemas_root,
        validate=validate,
        verbose=verbose,
        export_dk_csv=None,
    )
    stage_results.append(
        StageResult(
            name="sim",
            run_id=str(sim_res.get("run_id")),
            manifest_path=Path(str(sim_res.get("manifest_path"))),
            primary_output=str(sim_res.get("sim_results_path")),
        )
    )

    # Build bundle manifest
    bundle = {
        "schema_version": "0.1.0",
        "bundle_id": bundle_id,
        "slate_id": slate_id,
        "created_ts": _utc_now_iso(),
        "stages": [
            {
                "name": s.name,
                "run_id": s.run_id,
                "manifest": str(s.manifest_path),
                "primary_output": s.primary_output,
            }
            for s in stage_results
        ],
        "config": cfg,
    }
    bundle_path = bundle_dir / "bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    if verbose:
        print(
            f"[orchestrator] bundle={bundle_id} stages="
            f"{','.join(s.name for s in stage_results)}",
            file=sys.stderr,
        )

    return {"bundle_id": bundle_id, "bundle_path": str(bundle_path), "stages": [s.name for s in stage_results]}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m processes.orchestrator", description="Chain ingest→optimizer→variants→field→sim and create bundle.json")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--config-kv", nargs="*")
    p.add_argument("--out-root", type=Path, default=Path("data"))
    p.add_argument("--schemas-root", type=Path)
    p.add_argument("--validate", dest="validate", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        run_bundle(
            slate_id=str(args.slate_id),
            config_path=args.config,
            config_kv=args.config_kv,
            out_root=args.out_root,
            schemas_root=args.schemas_root,
            validate=bool(args.validate),
            dry_run=bool(args.dry_run),
            verbose=bool(args.verbose),
        )
    except Exception as e:  # pragma: no cover - error path
        print(f"[orchestrator] error: {e}", file=sys.stderr)
        return 1
    return 0
