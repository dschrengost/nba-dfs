#!/usr/bin/env python
"""
CLI shim: reads OptimizationRequest JSON on stdin, writes results JSON on stdout.
Bridges frontend contract -> legacy optimizer functional API.

Contract (stdin):
{
  site: "dk"|"fd",
  enginePreferred: "cp_sat"|"cbc",
  constraints: {...},          # optional; see processes/optimizer/types.py
  players: [ { name, team, position, salary, proj_fp, own_proj?, dk_id? } ],
  seed: int
}
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from itertools import combinations
from typing import Any

import pandas as pd

# Ensure repo root is on sys.path so `processes.*` is importable when running from scripts/
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# Ensure downstream helpers resolve paths relative to repo root
os.environ.setdefault("PROJECT_ROOT", _ROOT)


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _normalize_own(x):
    try:
        if x is None:
            return None
        v = float(x)
        return v / 100.0 if v > 1.5 else v
    except Exception:
        return None


def _detect_engine(preferred: str) -> str:
    if preferred == "cp_sat":
        try:
            import ortools  # noqa: F401

            return "cp_sat"
        except Exception:
            return "cbc"
    return "cbc"


def main() -> int:
    t0 = time.time()
    try:
        raw = sys.stdin.read()
        req = json.loads(raw)
    except Exception as e:
        out = {"ok": False, "error": f"Invalid JSON input: {e}"}
        sys.stdout.write(json.dumps(out))
        return 0

    site = str(req.get("site", "dk")).lower()
    engine_pref = str(req.get("enginePreferred", "cp_sat"))
    engine = _detect_engine(engine_pref)
    seed = int(req.get("seed", 42))

    # Build projections DataFrame from either inline `players` OR a file path
    players: list[dict[str, Any]] = req.get("players") or []
    projections_path = req.get("projectionsPath")

    def _norm_cols(df_in: pd.DataFrame) -> pd.DataFrame:
        df_in.columns = (
            df_in.columns.str.strip()
            .str.lower()
            .str.replace("%", "", regex=False)
            .str.replace(" ", "_", regex=False)
        )
        return df_in

    def _pick(colset, *cands):
        for c in cands:
            if c in colset:
                return c
        return None

    if players:
        rows: list[dict[str, Any]] = []
        for p in players:
            pos = p.get("position") or ""
            if isinstance(pos, list):
                pos = "/".join([str(s).upper() for s in pos])
            name = p.get("name") or p.get("player_name") or ""
            dk_id = p.get("dk_id") or p.get("player_id_dk") or p.get("player_id")
            # accept Own%/own/ownership keys too if present
            own_raw = p.get("own_proj", p.get("ownership", p.get("own", p.get("ownp"))))
            rows.append(
                {
                    "name": name,
                    "team": (p.get("team") or "").upper(),
                    "position": pos,
                    "salary": int(p.get("salary", 0) or 0),
                    "proj_fp": float(p.get("proj_fp", p.get("proj", 0.0)) or 0.0),
                    "own_proj": _normalize_own(own_raw),
                    "dk_id": None if dk_id is None else str(dk_id),
                }
            )
        df = pd.DataFrame(rows)

    elif projections_path:
        p = str(projections_path)
        # resolve relative to repo root
        if not os.path.isabs(p):
            p = os.path.join(_ROOT, p)
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext in (".csv", ".txt"):
                df_raw = pd.read_csv(p)
            elif ext in (".json",):
                df_raw = pd.read_json(p, orient="records")
            elif ext in (".parquet", ".pq"):
                df_raw = pd.read_parquet(p)
            else:
                raise ValueError(f"Unsupported projections file type: {ext}")
        except Exception as e:
            out = {"ok": False, "error": f"Failed to read projectionsPath '{p}': {e}"}
            sys.stdout.write(json.dumps(out))
            return 0

        df_raw = _norm_cols(df_raw)
        cols = set(df_raw.columns)

        # alias resolution
        c_name = _pick(cols, "name", "player", "player_name")
        c_team = _pick(cols, "team", "teamabbrev")
        c_pos = _pick(cols, "position", "pos", "positions")
        c_sal = _pick(cols, "salary", "sal")
        c_proj = _pick(cols, "proj_fp", "fpts", "fieldfpts", "proj", "projection")
        c_own = _pick(cols, "own_proj", "own", "ownership", "ownp", "own_percent")
        c_dkid = _pick(cols, "dk_id", "player_id_dk", "player_id", "id")

        if not all([c_name, c_team, c_pos, c_sal, c_proj]):
            missing = [
                x
                for x, c in [
                    ("name", c_name),
                    ("team", c_team),
                    ("position", c_pos),
                    ("salary", c_sal),
                    ("proj_fp", c_proj),
                ]
                if c is None
            ]
            out = {
                "ok": False,
                "error": f"Missing required columns after normalization: {missing}",
            }
            sys.stdout.write(json.dumps(out))
            return 0

        # build normalized dataframe
        def _pos_to_str(v):
            if isinstance(v, list):
                return "/".join([str(s).upper() for s in v])
            return str(v)

        df = pd.DataFrame(
            {
                "name": df_raw[c_name],
                "team": df_raw[c_team].astype(str).str.upper(),
                "position": df_raw[c_pos].apply(_pos_to_str),
                "salary": pd.to_numeric(df_raw[c_sal], errors="coerce").fillna(0).astype(int),
                "proj_fp": pd.to_numeric(df_raw[c_proj], errors="coerce").fillna(0.0).astype(float),
                "own_proj": (
                    pd.to_numeric(df_raw[c_own], errors="coerce").map(_normalize_own)
                    if c_own
                    else None
                ),
                "dk_id": df_raw[c_dkid].astype(str) if c_dkid else None,
            }
        )

        # if no ownership column found, fill with None (later becomes 0.0 if penalty off)
        if "own_proj" not in df or df["own_proj"] is None:
            df["own_proj"] = None

    else:
        out = {
            "ok": False,
            "error": "No players provided and no projectionsPath specified.",
        }
        sys.stdout.write(json.dumps(out))
        return 0

    # --- DK ID wiring: drop empty dk_id, optionally merge playerIdsPath ---
    # If dk_id exists but is entirely empty, drop it so the matcher/merge will run
    if "dk_id" in locals() and isinstance(df, pd.DataFrame) and "dk_id" in df.columns:
        if df["dk_id"].notna().sum() == 0:
            df = df.drop(columns=["dk_id"])

    # Prepare optional player_ids_df for backend; also best-effort merge into df
    player_ids_df = None
    player_ids_path = req.get("playerIdsPath")
    if player_ids_path:
        pid_path = str(player_ids_path)
        if not os.path.isabs(pid_path):
            pid_path = os.path.join(_ROOT, pid_path)
        pid_ext = os.path.splitext(pid_path)[1].lower()
        try:
            if pid_ext in (".csv", ".txt"):
                _pid = pd.read_csv(pid_path)
            elif pid_ext in (".json",):
                _pid = pd.read_json(pid_path, orient="records")
            elif pid_ext in (".parquet", ".pq"):
                _pid = pd.read_parquet(pid_path)
            else:
                raise ValueError(f"Unsupported playerIds file type: {pid_ext}")
        except Exception as e:
            _stderr(f"[playerIds] Failed to read '{pid_path}': {e}")
            _pid = None

        if _pid is not None:
            _pid = _norm_cols(_pid)
            cols_pid = set(_pid.columns)
            c_name = _pick(cols_pid, "name", "player", "player_name")
            c_team = _pick(cols_pid, "team", "teamabbrev")
            c_pos = _pick(cols_pid, "position", "pos")
            c_dkid = _pick(cols_pid, "dk_id", "player_id_dk", "player_id", "id")
            if not c_dkid:
                _stderr(
                    "[playerIds] No DK ID column found (expected one of: dk_id, player_id_dk, player_id, id)"
                )
            else:
                # Normalize slim IDs table
                pid_cols = {"dk_id": _pid[c_dkid].astype(str)}
                if c_name:
                    pid_cols["name"] = _pid[c_name].astype(str)
                if c_team:
                    # teamabbrev -> TEAM
                    tseries = _pid[c_team].astype(str).str.upper()
                    pid_cols["team"] = tseries
                if c_pos:
                    pid_cols["position"] = _pid[c_pos].astype(str)
                player_ids_df = pd.DataFrame(pid_cols)

                # Best-effort merge into df on (name, team)
                if "df" in locals() and isinstance(df, pd.DataFrame):
                    # ensure df team uppercase for the join
                    if "team" in df.columns:
                        df["team"] = df["team"].astype(str).str.upper()
                    join_keys = [
                        k
                        for k in ["name", "team"]
                        if k in df.columns and k in player_ids_df.columns
                    ]
                    if join_keys:
                        pid_slim = player_ids_df.drop_duplicates(
                            subset=(
                                ["dk_id"] + join_keys
                                if "dk_id" in player_ids_df.columns
                                else join_keys
                            )
                        )
                        df = df.merge(pid_slim, on=join_keys, how="left", suffixes=("", "_pid"))
                        # If we already had a dk_id col, prefer non-null union; else adopt merged dk_id
                        if "dk_id" in df.columns and "dk_id_pid" in df.columns:
                            df["dk_id"] = df["dk_id"].where(df["dk_id"].notna(), df["dk_id_pid"])
                            df = df.drop(
                                columns=[c for c in df.columns if c.endswith("_pid")],
                                errors="ignore",
                            )
                        elif "dk_id_pid" in df.columns:
                            df = df.rename(columns={"dk_id_pid": "dk_id"})

    # Import functional API and Constraints shim
    try:
        from processes.optimizer._legacy.nba_optimizer_functional import (
            optimize_with_diagnostics,
        )
        from processes.optimizer.types import Constraints
    except Exception as e:  # pragma: no cover - surface clean error
        out = {
            "ok": False,
            "error": f"Optimizer backend import failed: {e}",
        }
        sys.stdout.write(json.dumps(out))
        return 0

    # Build constraints (allow passthrough dict from caller)
    cons_in: dict[str, Any] = req.get("constraints") or {}
    # Map common caller knobs if present
    max_salary = cons_in.get("max_salary") or cons_in.get("salary_cap") or None
    min_salary = cons_in.get("min_salary")
    team_cap = (
        cons_in.get("global_team_limit") or cons_in.get("team_cap") or cons_in.get("maxPerTeam")
    )
    N_lineups = int(cons_in.get("N_lineups") or cons_in.get("n_lineups") or 1)
    unique_players = int(cons_in.get("unique_players") or cons_in.get("uniques") or 0)
    randomness_pct = float(cons_in.get("randomness_pct") or cons_in.get("randomnessPct") or 0.0)
    ownership_penalty = cons_in.get("ownership_penalty")
    cp_sat_params = cons_in.get("cp_sat_params") or {}

    cons = Constraints.from_dict(
        {
            "N_lineups": N_lineups,
            "unique_players": unique_players,
            "max_salary": max_salary,
            "min_salary": min_salary,
            "global_team_limit": team_cap,
            "team_limits": cons_in.get("team_limits") or {},
            "lock_ids": cons_in.get("lock_ids") or [],
            "ban_ids": cons_in.get("ban_ids") or [],
            "proj_min": float(cons_in.get("proj_min") or 0.0),
            "randomness_pct": randomness_pct,
            "cp_sat_params": cp_sat_params,
            "ownership_penalty": ownership_penalty,
        }
    )

    try:
        from contextlib import redirect_stdout

        # Redirect noisy prints from legacy backend to stderr so stdout stays JSON-only
        with redirect_stdout(sys.stderr):
            lineups, diagnostics = optimize_with_diagnostics(
                df, cons, int(seed), site, player_ids_df=player_ids_df, engine=engine
            )
        elapsed_ms = int(round((time.time() - t0) * 1000))

        # Convert to JSON-able structure
        def pl2json(pl) -> dict[str, Any]:
            return {
                "player_id": pl.player_id,
                "name": pl.name,
                "pos": pl.pos,
                "team": pl.team,
                "salary": pl.salary,
                "proj": pl.proj,
                "dk_id": pl.dk_id,
                "own_proj": pl.own_proj,
            }

        out_lineups = [
            {
                "lineup_id": lu.lineup_id,
                "total_proj": lu.total_proj,
                "total_salary": lu.total_salary,
                "players": [pl2json(pl) for pl in lu.players],
            }
            for lu in (lineups or [])
        ]

        # --- Pool metrics for diagnostics -------------------------------------------------
        def _pool_metrics(out_lineups_json):
            """Compute quick diversity metrics & exposures for the returned lineups."""
            try:
                lineups_list = out_lineups_json or []
                # Prefer dk_id, fallback to player_id
                lid_lists = [
                    [(p.get("dk_id") or p.get("player_id")) for p in lu.get("players", [])]
                    for lu in lineups_list
                ]
                # Filter out Nones defensively
                lid_lists = [[x for x in lst if x is not None] for lst in lid_lists]
                sets = [set(lst) for lst in lid_lists if lst]
                # Pairwise overlap / Jaccard
                pairs = list(combinations(sets, 2))
                overlaps = [(len(a & b)) for a, b in pairs] if pairs else []
                jaccards = [(len(a & b) / max(1, len(a | b))) for a, b in pairs] if pairs else []
                # Exposures by player id
                counts = Counter([pid for lst in lid_lists for pid in lst])
                n_lineups = len(lid_lists) or 1
                exposures = {pid: c / n_lineups for pid, c in counts.items()}
                return {
                    "lineups": len(lid_lists),
                    "avg_overlap_players": ((sum(overlaps) / len(overlaps)) if overlaps else 0.0),
                    "avg_pairwise_jaccard": ((sum(jaccards) / len(jaccards)) if jaccards else 0.0),
                    "unique_player_count": len(set().union(*sets)) if sets else 0,
                    "exposures": exposures,
                }
            except Exception:
                return {
                    "lineups": 0,
                    "avg_overlap_players": 0.0,
                    "avg_pairwise_jaccard": 0.0,
                    "unique_player_count": 0,
                    "exposures": {},
                }

        pool_diag = _pool_metrics(out_lineups)

        # Helper: scrub JSON for non-finite numbers (Infinity/NaN) so JS JSON.parse succeeds
        import math

        def _clean_nans(obj):
            if isinstance(obj, float):
                return obj if math.isfinite(obj) else None
            if isinstance(obj, dict):
                return {k: _clean_nans(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean_nans(v) for v in obj]
            return obj

        # Ensure diagnostics are JSON-serializable (handle numpy types)
        try:
            diag_safe = json.loads(json.dumps(diagnostics, default=lambda o: str(o)))
        except Exception:
            diag_safe = diagnostics

        # Augment diagnostics with constraint echo for UI tags
        constraints_echo = None
        try:
            constraints_echo = cons.to_dict()  # type: ignore[attr-defined]
        except Exception:
            constraints_echo = None
        # Include raw constraints as well (to carry nested pruning if present)
        try:
            diag_safe = diag_safe or {}
            if isinstance(diag_safe, dict):
                diag_safe["constraints"] = constraints_echo
                diag_safe["constraints_raw"] = cons_in
                # Ensure penalty snapshot includes curve_type and weight if available
                pen = (
                    (constraints_echo or {}).get("ownership_penalty")
                    if isinstance(constraints_echo, dict)
                    else None
                )
                if pen:
                    oe = diag_safe.setdefault("ownership_penalty", {})
                    if "curve_type" not in oe and "curve_type" in pen:
                        oe["curve_type"] = pen.get("curve_type")
                    if "weight_lambda" not in oe and "weight_lambda" in pen:
                        oe["weight_lambda"] = pen.get("weight_lambda")
        except Exception:
            pass

        # Attach pool diagnostics
        try:
            diag_safe = diag_safe or {}
            if isinstance(diag_safe, dict):
                diag_safe["pool"] = pool_diag
        except Exception:
            pass

        out = {
            "ok": True,
            "engineUsed": engine,
            "lineups": out_lineups,
            "summary": {
                "tried": diagnostics.get("N", len(out_lineups)),
                "valid": len(out_lineups),
                "bestScore": max((lu["total_proj"] for lu in out_lineups), default=0.0),
                "elapsedMs": elapsed_ms,
                "invalidReasons": {"salary": 0, "slots": 0, "teamcap": 0, "dup": 0},
                # Keep original constraints echo for UI convenience
                "optionsUsed": cons_in,
            },
            "diagnostics": diag_safe,
        }

        # Auto-save run under runs/<SLATE_KEY>/optimizer (rolling keep=10)
        try:
            slate_key = str(req.get("slateKey") or "").strip()
            if not slate_key:
                try:
                    from src.runs.api import gen_slate_key  # type: ignore

                    slate_key = gen_slate_key()
                except Exception:
                    slate_key = time.strftime("%y-%m-%d_%H%M%S", time.gmtime())

            meta = {
                "schema_version": 1,
                "module": "optimizer",
                "slate_key": slate_key,
                "engine": {"solver": engine, "seed": seed},
                "params": {
                    "uniques": int(cons_in.get("unique_players", 0)),
                    "ownership_penalty": {
                        "enabled": bool(
                            (constraints_echo or {})
                            .get("ownership_penalty", {})
                            .get("enabled", False)
                        ),
                        "lambda": float(
                            (constraints_echo or {})
                            .get("ownership_penalty", {})
                            .get("weight_lambda", 0.0)
                        ),
                        "curve": str(
                            (constraints_echo or {})
                            .get("ownership_penalty", {})
                            .get("curve_type", "linear")
                        ),
                    },
                },
                "diagnostics": {"pool": pool_diag},
            }

            artifacts = {
                "lineups_json": out_lineups,
                "diagnostics_json": diag_safe,
                "summary_json": out["summary"],
            }

            from src.runs.api import save_run  # type: ignore

            saved = save_run(
                slate_key=slate_key,
                module="optimizer",
                meta=meta,
                artifacts=artifacts,
                keep_last=10,
            )
            out["run_id"] = saved.run_id
            out["slate_key"] = saved.slate_key
            out["run_path"] = str(saved.run_dir)
        except Exception as e:
            _stderr(f"[runs/save] Warning: failed to save run: {e}")

        out = _clean_nans(out)
        sys.stdout.write(json.dumps(out))
        return 0
    except Exception as e:
        out = {
            "ok": False,
            "error": f"Optimization failed: {e}",
        }
        sys.stdout.write(json.dumps(out))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
