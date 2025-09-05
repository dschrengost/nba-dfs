"""
Functional NBA DFS optimizer API for Streamlit integration
"""

import math
import random
import re
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pulp as plp
import pandas as pd
import os
import time
import hashlib

try:
    from difflib import SequenceMatcher

    FUZZY_MATCHING_AVAILABLE = True
except ImportError:
    FUZZY_MATCHING_AVAILABLE = False
from .types import Player, Lineup, Constraints, OptimizerError, ErrorCodes, SiteType
from .dk_strict_results import (
    lineups_to_grid_df,
    validate_grid_df,
    grid_df_to_dk_csv,
)
from .dk_data_loader import (
    DKDataConfig,
    load_dk_strict_projections,
    validate_dk_strict_data,
)

# Team name standardization
TEAM_REPLACEMENT_DICT = {
    "PHO": "PHX",
    "GS": "GSW",
    "SA": "SAS",
    "NO": "NOP",
    "NY": "NYK",
}


# ============================================================================
# PRP-18.2: DK-Strict Ownership Normalization Functions
# ============================================================================


def _normalize_projections_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Normalize projections DataFrame for DK-Strict mode (PRP-18.2)

    Maps ownership columns (Own%, ownership, etc.) to own_proj (0-1 scale)
    and provides other helpful column mappings for resilience.

    Args:
        df: Raw projections DataFrame

    Returns:
        Tuple of (normalized_df, normalization_info_dict)
    """
    if df is None or df.empty:
        return df, {"ownership": None}

    df_norm = df.copy()
    info = {"ownership": None}

    def _first_col(candidates):
        """Find first column that matches any of the candidates (case-insensitive)"""
        for candidate in candidates:
            for variant in (
                candidate,
                candidate.lower(),
                candidate.upper(),
                candidate.title(),
            ):
                if variant in df_norm.columns:
                    return variant
        return None

    # Map ownership → own_proj (PRIMARY PRP-18.2 requirement)
    ownership_candidates = [
        "own_proj",
        "own%",
        "ownership",
        "ownership%",
        "projected ownership",
        "own pct",
        "own_pct",
    ]
    own_col = _first_col(ownership_candidates)

    if own_col:
        # Convert to numeric, coerce non-numeric to NaN
        ser = pd.to_numeric(df_norm[own_col], errors="coerce").astype(float)

        # Determine if we need to scale (divide by 100)
        max_val = ser.max(skipna=True)
        # PRP-22: use 1.5 threshold to avoid double-scaling edge cases
        scaled_by = 100.0 if max_val and max_val > 1.5 else 1.0

        if scaled_by > 1.0:
            ser = ser / scaled_by

        # Clip to [0, 1] range
        ser = ser.clip(lower=0.0, upper=1.0)

        # Count non-numeric values that were dropped
        non_numeric_count = df_norm[own_col].shape[0] - ser.notna().sum()

        # Update DataFrame with normalized ownership
        df_norm["own_proj"] = ser

        # Record normalization info for telemetry
        info["ownership"] = {
            "source_col": own_col,
            "target_col": "own_proj",
            "scaled_by": scaled_by,
            "non_numeric_dropped": int(non_numeric_count),
            "clip_applied": True,
        }

    # Optional resilience mappings (no behavior change, just column name consistency)
    mapping = {
        "proj_fp": ["Fpts Proj", "Fpts_Proj", "FptsProj", "FPTS", "Proj", "Projection"],
        "salary": ["Salary", "SAL", "Salary($)"],
        "position": ["Roster Position", "Position", "POS"],
        "name": ["Name", "Player", "Player Name"],
        "team": ["TeamAbbrev", "Team", "TEAM", "Tm"],
        "dk_id": ["ID", "Id", "id"],
    }

    for target, candidates in mapping.items():
        if target not in df_norm.columns:
            col = _first_col(candidates)
            if col and col != target:
                df_norm = df_norm.rename(columns={col: target})

    return df_norm, info


# ============================================================================
# PRP-22: Ownership-only normalization helper (no other column renames)
# ============================================================================
def _normalize_ownership(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Normalize ownership to own_proj ∈ [0,1] from any common source column.
    Returns the updated DataFrame and a telemetry dict capturing normalization details.
    """
    if df is None or df.empty:
        return df, {
            "source_col": None,
            "scaled_by": 1.0,
            "scaled_by_100": False,
            "clip_applied": False,
            "non_numeric_dropped": 0,
            "nulls_filled": 0,
            "max_before": None,
            "max_after": None,
        }

    df_out = df.copy()

    lower_cols = {c.lower(): c for c in df_out.columns}
    candidates = [
        "own_proj",
        "own%",
        "ownership",
        "ownership%",
        "projected ownership",
        "own pct",
        "own_pct",
        "ownproj",
        "proj_own",
    ]
    src = None
    for cand in candidates:
        if cand in lower_cols:
            src = lower_cols[cand]
            break
    if src is None:
        # substring fallback
        for lc, orig in lower_cols.items():
            if "own" in lc:
                src = orig
                break
    if src is None:
        # No ownership column found; create a zero column so downstream contracts can pass
        df_out["own_proj"] = 0.0
        return df_out, {
            "source_col": None,
            "scaled_by": 1.0,
            "scaled_by_100": False,
            "clip_applied": False,
            "non_numeric_dropped": 0,
            "nulls_filled": 0,
            "max_before": 0.0,
            "max_after": 0.0,
        }

    raw = pd.to_numeric(df_out[src], errors="coerce").astype(float)
    max_before = float(raw.max(skipna=True)) if raw.notna().any() else None
    scaled_by = 100.0 if (max_before is not None and max_before > 1.5) else 1.0
    ser = raw.copy()
    if scaled_by > 1.0:
        ser = ser / scaled_by
    # Count nulls and fill with 0.0 per PRP hardening
    nulls_before = int(ser.isna().sum())
    ser = ser.fillna(0.0)
    # Clip to [0,1]
    clipped_series = ser.clip(0.0, 1.0)
    num_clipped = int((clipped_series.ne(ser)).sum())
    ser = clipped_series
    max_after = float(ser.max(skipna=True)) if ser.notna().any() else None
    non_num_dropped = int(df_out[src].shape[0] - raw.notna().sum())

    df_out["own_proj"] = ser
    return df_out, {
        "source_col": src,
        "scaled_by": scaled_by,
        "scaled_by_100": bool(scaled_by > 1.0),
        "clip_applied": True,
        "non_numeric_dropped": non_num_dropped,
        "nulls_filled": nulls_before,
        "max_before": max_before,
        "max_after": max_after,
        "num_clipped": num_clipped,
    }


def fuzzy_similarity(name1: str, name2: str) -> float:
    """Calculate fuzzy string similarity between two names (0.0 to 1.0)"""
    if not FUZZY_MATCHING_AVAILABLE:
        return 1.0 if name1.lower() == name2.lower() else 0.0

    # Normalize names for comparison
    norm1 = re.sub(r"[^\w\s]", "", name1.lower()).strip()
    norm2 = re.sub(r"[^\w\s]", "", name2.lower()).strip()

    if not norm1 or not norm2:
        return 0.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def normalize_player_name(name: str) -> str:
    """Enhanced player name normalization for better matching"""
    if pd.isna(name):
        return ""

    # Convert to string and basic cleanup
    name = str(name).strip()

    # Common name variations and standardizations
    name_replacements = {
        # Handle common nicknames and variations
        "Jr.": "Jr",
        "Sr.": "Sr",
        "III": "III",
        "II": "II",
        "IV": "IV",
        "V": "V",
    }

    for old, new in name_replacements.items():
        name = name.replace(old, new)

    # Remove extra whitespace and normalize case
    name = " ".join(name.split()).lower()

    return name


def find_fuzzy_matches(
    proj_df: pd.DataFrame, ids_df: pd.DataFrame, similarity_threshold: float = 0.85
) -> pd.DataFrame:
    """
    Find fuzzy matches between projections and ID data when exact matching fails

    Returns DataFrame with fuzzy match suggestions
    """
    if not FUZZY_MATCHING_AVAILABLE:
        return pd.DataFrame()

    # Get unmatched projections
    unmatched = proj_df[proj_df["dk_id"].isna()].copy()
    if unmatched.empty:
        return pd.DataFrame()

    print(f"🔍 Attempting fuzzy matching for {len(unmatched)} unmatched players...")

    fuzzy_matches = []

    for _, proj_row in unmatched.iterrows():
        proj_name = normalize_player_name(proj_row["name"])
        proj_team = proj_row["__team_norm"]

        best_match = None
        best_similarity = 0.0

        for _, id_row in ids_df.iterrows():
            id_name = normalize_player_name(id_row["name_ids"])
            id_team = id_row["__team_norm"]

            # Only consider same team matches for safety
            if proj_team == id_team:
                similarity = fuzzy_similarity(proj_name, id_name)
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = id_row

        if best_match is not None:
            fuzzy_matches.append(
                {
                    "proj_name": proj_row["name"],
                    "id_name": best_match["name_ids"],
                    "team": proj_team,
                    "similarity": best_similarity,
                    "dk_id": best_match["dk_id"],
                    "proj_index": proj_row.name,
                }
            )

    fuzzy_df = pd.DataFrame(fuzzy_matches)
    if not fuzzy_df.empty:
        print(f"🎯 Found {len(fuzzy_df)} potential fuzzy matches:")
        for _, match in fuzzy_df.head(5).iterrows():
            print(
                f"  {match['proj_name']} → {match['id_name']} ({match['similarity']:.1%} similar)"
            )

    return fuzzy_df


# ============================================================================
# PRP-16: Ownership Penalty Functions
# ============================================================================


def _clamp(v: float, lo: float, hi: float) -> float:
    """Clamp value to range [lo, hi]"""
    return max(lo, min(hi, v))


def _effective_p(p: float, p0: float, gamma: float, lo: float, hi: float) -> float:
    """Calculate effective ownership percentage with shrinkage and clamping"""
    return _clamp(gamma * p + (1.0 - gamma) * p0, lo, hi)


def _g_curve(p_eff: float, settings) -> float:
    """Calculate penalty curve value for effective ownership percentage"""
    if settings.curve_type == "linear":
        return p_eff
    elif settings.curve_type == "power":
        return p_eff**settings.power_k
    elif settings.curve_type == "neglog":
        return -math.log(max(1e-9, 1.0 - p_eff))
    else:  # Default: sigmoid
        eps = 1e-9
        ratio = settings.pivot_p0 / max(eps, p_eff)
        return 1.0 / (1.0 + (ratio**settings.curve_alpha))


def _per_player_penalty_terms(own_series, settings) -> Dict[str, float]:
    """Calculate penalty terms for each player based on ownership and curve settings"""
    g = {}
    for pid, p in own_series.items():
        p_eff = _effective_p(
            float(p),
            settings.pivot_p0,
            settings.shrink_gamma,
            settings.clamp_min,
            settings.clamp_max,
        )
        g[pid] = _g_curve(p_eff, settings)
    return g


# New helper: _objective_coeffs_from_players
def _objective_coeffs_from_players(
    players: List[Dict], settings, lam: float
) -> Dict[str, float]:
    """Calculate objective coefficients from the in-memory players list.
    Returns dict[player_id] -> adjusted points (base - lam * g(p))."""
    coeffs: Dict[str, float] = {}
    for p in players:
        pid = p["player_id"]
        base = float(p["proj"])
        own = p.get("own_proj", None)
        if own is None:
            coeffs[pid] = base
            continue
        # normalize to [0,1]
        own_pct = own / 100.0 if own > 1.0 else float(own)
        p_eff = _effective_p(
            own_pct,
            settings.pivot_p0,
            settings.shrink_gamma,
            settings.clamp_min,
            settings.clamp_max,
        )
        gval = _g_curve(p_eff, settings)
        coeffs[pid] = base - lam * gval
    return coeffs


def _objective_coeffs(
    projections_df: pd.DataFrame, settings, lam: float
) -> Dict[str, float]:
    """Calculate objective coefficients with ownership penalty"""
    # Expect columns: 'player_id', 'proj_fp', 'own%' (own in [0,1] or percentage)
    own_col = "own%" if "own%" in projections_df.columns else "own_proj"

    if own_col not in projections_df.columns:
        # No ownership data - return base projections
        coeffs = {}
        for row in projections_df.itertuples(index=False):
            pid = getattr(row, "player_id", f"{row.name}_{row.team}_{row.salary}")
            coeffs[pid] = float(row.proj_fp)
        return coeffs

    # Normalize ownership to [0, 1] if needed
    own_series = projections_df.set_index("player_id")[own_col]
    if own_series.max() > 1.0:
        own_series = own_series / 100.0  # Convert percentage to decimal

    own_g = _per_player_penalty_terms(own_series, settings)

    coeffs = {}
    for row in projections_df.itertuples(index=False):
        pid = getattr(row, "player_id", f"{row.name}_{row.team}_{row.salary}")
        base = float(row.proj_fp)
        penalty = lam * own_g.get(pid, 0.0)
        coeffs[pid] = base - penalty
    return coeffs


def _lineup_raw_projection(
    lineup_players: List[str], proj_map: Dict[str, float]
) -> float:
    """Calculate raw projection total for a lineup (no penalty)"""
    return sum(proj_map.get(pid, 0.0) for pid in lineup_players)


def _measure_offoptimal_pct(
    P_star: float, lineup_players: List[str], proj_map: Dict[str, float]
) -> float:
    """Measure how far off optimal this lineup is (as percentage)"""
    P = _lineup_raw_projection(lineup_players, proj_map)
    if P_star <= 0:
        return 0.0
    return max(0.0, 1.0 - (P / P_star))


def _g_curve_penalty(own_pct: float, settings) -> float:
    """Calculate penalty curve value for ownership percentage (for CBC solver)"""
    p_eff = _effective_p(
        own_pct,
        settings.pivot_p0,
        settings.shrink_gamma,
        settings.clamp_min,
        settings.clamp_max,
    )
    return _g_curve(p_eff, settings)


def _solve_with_lambda(
    lam: float, players: List[Dict], settings, build_and_solve_fn
) -> List[str]:
    """Solve optimization problem with specific lambda penalty weight using provided coeffs."""
    coeffs = _objective_coeffs_from_players(players, settings, lam)
    lineup_players = build_and_solve_fn(coeffs)
    return lineup_players


def _find_lambda_by_percent(
    target_pct: float,
    tol_pct: float,
    players: List[Dict],
    settings,
    build_and_solve_fn,
    proj_map: Dict[str, float],
    lambda_seed: float = 1.0,
    lambda_cap: float = 12.0,
) -> Tuple[float, float, List[str]]:
    """
    Find lambda value to achieve target off-optimal percentage using bracket + bisection

    Returns:
        Tuple of (lambda_used, achieved_offoptimal_pct, lineup_players)
    """
    # Baseline P* (optimal with no penalty)
    lineup_star = _solve_with_lambda(0.0, players, settings, build_and_solve_fn)
    P_star = _lineup_raw_projection(lineup_star, proj_map)

    if target_pct <= 0:
        return 0.0, 0.0, lineup_star

    # Bracket: start with lambda_low = 0, find lambda_high that exceeds target
    lam_lo, lo_players = 0.0, lineup_star
    off_lo = _measure_offoptimal_pct(P_star, lo_players, proj_map)

    lam_hi = max(1e-6, lambda_seed)
    lam_hi = min(lambda_cap, lam_hi)
    hi_players = _solve_with_lambda(lam_hi, players, settings, build_and_solve_fn)
    off_hi = _measure_offoptimal_pct(P_star, hi_players, proj_map)

    # Double lambda_hi until we exceed target or hit cap
    while off_hi < target_pct and lam_hi < lambda_cap:
        lam_lo, off_lo = lam_hi, off_hi
        lam_hi = min(lambda_cap, lam_hi * 2.0)
        hi_players = _solve_with_lambda(lam_hi, players, settings, build_and_solve_fn)
        off_hi = _measure_offoptimal_pct(P_star, hi_players, proj_map)

    # If cap can't reach target, return closest
    if off_hi < target_pct:
        return (
            (lam_hi, off_hi, hi_players)
            if abs(off_hi - target_pct) <= abs(off_lo - target_pct)
            else (lam_lo, off_lo, lo_players)
        )

    # Bisection search
    best = (lam_hi, off_hi, hi_players)
    for _ in range(18):  # ~18 iterations for good precision
        lam_mid = 0.5 * (lam_lo + lam_hi)
        mid_players = _solve_with_lambda(lam_mid, players, settings, build_and_solve_fn)
        off_mid = _measure_offoptimal_pct(P_star, mid_players, proj_map)

        if abs(off_mid - target_pct) <= tol_pct:
            return lam_mid, off_mid, mid_players

        if abs(off_mid - target_pct) < abs(best[1] - target_pct):
            best = (lam_mid, off_mid, mid_players)

        if off_mid < target_pct:
            lam_lo, off_lo = lam_mid, off_mid
        else:
            lam_hi, off_hi = lam_mid, off_mid

    return best


def optimize(
    projections_df: pd.DataFrame,
    constraints: Constraints,
    seed: int,
    site: SiteType,
    player_ids_df: Optional[pd.DataFrame] = None,
    engine: str = "cbc",
) -> List[Lineup]:
    """
    Main optimization function - returns lineups only (for compatibility)
    """
    lineups, _ = optimize_with_diagnostics(
        projections_df, constraints, seed, site, player_ids_df, engine=engine
    )
    return lineups


def optimize_with_diagnostics(
    projections_df: pd.DataFrame,
    constraints: Constraints,
    seed: int,
    site: SiteType,
    player_ids_df: Optional[pd.DataFrame] = None,
    engine: str = "cbc",
) -> Tuple[List[Lineup], Dict[str, Any]]:
    """
    Main optimization function for UI integration

    Args:
        projections_df: Player projections with required columns
        constraints: Validated optimization constraints
        seed: Random seed for deterministic behavior
        site: "dk" or "fd"
        player_ids_df: Optional DataFrame with real DK/FD player IDs

    Returns:
        List of optimized lineups

    Raises:
        OptimizerError: For all optimization failures
    """
    # Set seeds for deterministic behavior
    random.seed(seed)
    np.random.seed(seed)

    # Validate projections data
    validate_projections(projections_df, site)

    # Attach real player IDs if available
    # Snapshot columns before merges for diagnostics
    _cols_before_merge = sorted(list(projections_df.columns))

    projections_df, id_diagnostics = attach_player_ids_if_available(
        projections_df, site, player_ids_df
    )

    # PRP-Ownership-Normalization: Normalize ownership and capture telemetry
    try:
        projections_df, own_norm = _normalize_ownership(projections_df)
        norm_block = id_diagnostics.setdefault("normalization", {}).setdefault(
            "ownership", {}
        )
        if own_norm:
            norm_block.update(own_norm)
        # Add post-merge columns diff
        _cols_after_merge = sorted(list(projections_df.columns))
        norm_block["cols_diff_post_merge"] = list(
            set(_cols_before_merge) ^ set(_cols_after_merge)
        )
        try:
            if "own_proj" in projections_df.columns:
                norm_block["own_proj_max_post_merge"] = float(
                    projections_df["own_proj"].max()
                )
        except Exception:
            pass
    except Exception:
        pass
    # Snapshot whether ownership penalty was requested (for UI gating)
    try:
        pen_cfg = getattr(constraints, "ownership_penalty", None)
        id_diagnostics.setdefault("constraints_snapshot", {})["ownership_enabled"] = (
            bool(pen_cfg and pen_cfg.enabled)
        )
    except Exception:
        pass

    # Handle ID matching failures
    if id_diagnostics["errors"]:
        for error in id_diagnostics["errors"]:
            print(f"❌ {error}")

    if id_diagnostics["warnings"]:
        for warning in id_diagnostics["warnings"]:
            print(f"⚠️  {warning}")

    # Check if we should fail fast for DK export requirements
    success_rate = id_diagnostics["success_rate"]

    # Fail-fast mode: block optimization if DK ID requirements not met
    if constraints.require_dk_ids and site == "dk":
        if success_rate < constraints.min_dk_id_match_rate:
            raise OptimizerError(
                code="INSUFFICIENT_DK_IDS",
                message=f"DK ID match rate ({success_rate:.1f}%) below required minimum ({constraints.min_dk_id_match_rate}%)",
                user_message=f"""❌ Cannot proceed: Insufficient DK player IDs

Required: {constraints.min_dk_id_match_rate}% match rate
Actual: {success_rate:.1f}% ({id_diagnostics['matched_players']}/{id_diagnostics['total_players']} players)

🔧 How to fix:
1. Add dk_data/player_ids.csv with columns: ID, Name, TeamAbbrev, Position
2. Ensure player names and teams match between projections and player_ids.csv
3. Export player IDs from DraftKings contest entries
4. Or disable fail-fast mode (require_dk_ids=False) to use synthetic IDs

📊 Diagnostics:
• Data source: {id_diagnostics['data_source'] or 'None'}
• Name/team matching failed: {id_diagnostics['failed_name_matching']} players
• Position validation failed: {id_diagnostics['failed_position_validation']} players""",
                details=id_diagnostics,
            )

    # Warning mode: inform about compatibility issues
    elif site == "dk" and success_rate < 95.0:
        print(f"\n🚨 WARNING: Low DK ID match rate ({success_rate:.1f}%)")
        print("   Lineups generated will NOT be compatible with DraftKings import!")
        print(
            "   Enable fail-fast mode (require_dk_ids=True) to prevent invalid lineups."
        )
        print("   See diagnostics above for specific matching failures.\n")

    # Convert DataFrame to player dictionary format
    players = convert_projections_to_players(projections_df, constraints.proj_min)

    if len(players) == 0:
        raise OptimizerError(
            code=ErrorCodes.INVALID_PROJECTIONS,
            message="No players meet minimum projection threshold",
            user_message=f"No players found with projections >= {constraints.proj_min}. Try lowering the minimum.",
            details={
                "proj_min": constraints.proj_min,
                "available_players": len(projections_df),
            },
        )

    # If by_percent mode is requested, find λ first for CP-SAT engines (use CP-SAT during search)
    ownership_penalty = constraints.ownership_penalty
    if (
        ownership_penalty
        and ownership_penalty.enabled
        and ownership_penalty.mode == "by_percent"
        and engine in ("cp_sat", "cp_sat_counts")
    ):
        print(
            f"🎯 Ownership penalty: by % off optimal (target: {ownership_penalty.target_offoptimal_pct:.1%})"
        )

        # Build projection map for off-optimal calculation
        players_for_search = convert_projections_to_players(
            projections_df, constraints.proj_min
        )
        proj_map = {p["player_id"]: p["proj"] for p in players_for_search}

        # Build-and-solve using CP-SAT by injecting adjusted coefficients as temporary projections
        def build_and_solve_fn(coeffs: Dict[str, float]) -> List[str]:
            # Adjust player projections to the provided coefficients (base - λ*g(p))
            players_adj: List[Dict] = []
            for p in players_for_search:
                q = dict(p)
                q["proj"] = float(coeffs.get(p["player_id"], p["proj"]))
                players_adj.append(q)
            # Prepare a minimal CP-SAT run: disable penalty (coeffs already include it), single lineup, short time cap
            base_constraints = Constraints.from_dict(constraints.to_dict())
            if (
                hasattr(base_constraints, "ownership_penalty")
                and base_constraints.ownership_penalty
            ):
                base_constraints.ownership_penalty.enabled = False
            base_constraints.N_lineups = 1
            if isinstance(base_constraints.cp_sat_params, dict):
                params = dict(base_constraints.cp_sat_params)
                mt = float(params.get("max_time_seconds", 0.7) or 0.7)
                params["max_time_seconds"] = max(0.25, min(mt, 1.0))
                params["num_search_workers"] = int(
                    params.get("num_search_workers", 0) or 0
                )
                base_constraints.cp_sat_params = params
            try:
                from .solvers.cpsat_solver import (
                    solve_cpsat_iterative,
                    solve_cpsat_iterative_counts,
                )

                if engine == "cp_sat_counts":
                    _lineups, _diag = solve_cpsat_iterative_counts(
                        players_adj, base_constraints, seed, site
                    )
                else:
                    _lineups, _diag = solve_cpsat_iterative(
                        players_adj, base_constraints, seed, site
                    )
            except Exception:
                return []
            if not _lineups:
                return []
            return [pl.player_id for pl in _lineups[0].players]

        lam_used, achieved_pct, _ = _find_lambda_by_percent(
            target_pct=ownership_penalty.target_offoptimal_pct,
            tol_pct=ownership_penalty.tol_offoptimal_pct,
            players=players_for_search,
            settings=ownership_penalty,
            build_and_solve_fn=build_and_solve_fn,
            proj_map=proj_map,
        )
        print(
            f"🎯 Lambda search result: λ={lam_used:.3f}, achieved {achieved_pct:.1%} off-optimal (CP-SAT)"
        )
        ownership_penalty.weight_lambda = lam_used
        ownership_penalty.mode = "by_points"  # Use fixed λ for downstream engine
        # Stash into diagnostics for UI
        id_diagnostics.setdefault("ownership_penalty", {})
        id_diagnostics["ownership_penalty"].update(
            {
                "enabled": True,
                "mode": "by_percent",
                "lambda_used": float(lam_used),
                "target_offoptimal_pct": float(
                    constraints.ownership_penalty.target_offoptimal_pct
                ),
                "achieved_offoptimal_pct": float(achieved_pct),
                "capped": bool(lam_used >= 12.0 - 1e-9),
            }
        )

    # Choose engine path
    if engine == "cp_sat":
        print(f"🔧 Using CP-SAT solver engine (seed={seed}, site={site})")
        try:
            from .solvers.cpsat_solver import solve_cpsat_iterative
        except Exception as e:
            raise OptimizerError(
                code=ErrorCodes.CONFIG_ERROR,
                message=f"CP-SAT engine unavailable: {e}",
                user_message="CP-SAT engine is not available. Please install ortools or switch to CBC.",
                details={"import_error": str(e)},
            )

        lineups, diagnostics = solve_cpsat_iterative(players, constraints, seed, site)
        # Merge DK ID diagnostics into solver diagnostics for consistency
        if not isinstance(diagnostics, dict):
            diagnostics = {}
        diagnostics.update(id_diagnostics)
        # Ensure engine key present
        diagnostics.setdefault("engine", "cp_sat")
        # Compute achieved % off optimal against a CP-SAT baseline (λ=0) on produced lineups
        try:
            pen_cfg = getattr(constraints, "ownership_penalty", None)
            if pen_cfg and pen_cfg.enabled and lineups:
                # Build a minimal baseline CP-SAT run (λ=0, N=1) for P* using same constraints
                from copy import deepcopy as _deepcopy

                base_constraints = Constraints.from_dict(constraints.to_dict())
                # Disable ownership penalty and reduce to a single lineup with a short time cap if provided
                if (
                    hasattr(base_constraints, "ownership_penalty")
                    and base_constraints.ownership_penalty
                ):
                    base_constraints.ownership_penalty.enabled = False
                base_constraints.N_lineups = 1
                # Soften time limit for the baseline solve if present
                if isinstance(base_constraints.cp_sat_params, dict):
                    params = dict(base_constraints.cp_sat_params)
                    mt = float(params.get("max_time_seconds", 0.7) or 0.7)
                    params["max_time_seconds"] = max(0.25, min(mt, 1.0))
                    base_constraints.cp_sat_params = params
                baseline_lineups, _baseline_diag = solve_cpsat_iterative(
                    players, base_constraints, seed, site
                )
                if baseline_lineups:
                    # Raw projection sums (points-only) for baseline and first produced lineup
                    def _sum_proj(lu):
                        return float(sum(p.proj for p in lu.players))

                    P_star = _sum_proj(baseline_lineups[0])
                    P_cur = _sum_proj(lineups[0])
                    off_pct = 0.0 if P_star <= 0 else max(0.0, 1.0 - (P_cur / P_star))
                    _ep = diagnostics.get("ownership_penalty", {})
                    # Preserve any target set earlier; just annotate achieved
                    _ep["achieved_offoptimal_pct"] = float(off_pct)
                    diagnostics["ownership_penalty"] = _ep
        except Exception:
            # Non-fatal; skip achieved% calculation if anything fails
            pass
        # Add ownership penalty diagnostics for CP-SAT (post-solve)
        try:
            pen_cfg = getattr(constraints, "ownership_penalty", None)
            if pen_cfg and pen_cfg.enabled:
                pen_diag: Dict[str, Any] = {
                    "enabled": True,
                    "mode": pen_cfg.mode,
                    "lambda_used": float(getattr(pen_cfg, "weight_lambda", 0.0) or 0.0),
                    "applied": False,
                    "reason": None,
                }
                # If no ownership available on any player, flag error
                any_own = any(p.get("own_proj") is not None for p in players)
                if not any_own:
                    pen_diag["applied"] = False
                    pen_diag["reason"] = "missing_or_invalid_own_proj"
                else:
                    # Compute averages over produced lineups
                    lam = float(getattr(pen_cfg, "weight_lambda", 0.0) or 0.0)
                    if lam > 0 and lineups:
                        chalk_vals = []
                        penalty_pts = []
                        for lu in lineups:
                            gvals = []
                            for pl in lu.players:
                                if pl.own_proj is None:
                                    continue
                                own_pct = (
                                    pl.own_proj / 100.0
                                    if pl.own_proj > 1.0
                                    else float(pl.own_proj)
                                )
                                g = _g_curve_penalty(own_pct, pen_cfg)
                                gvals.append(g)
                            if gvals:
                                chalk_vals.append(float(np.mean(gvals)))
                                penalty_pts.append(float(lam * np.sum(gvals)))
                        if chalk_vals:
                            pen_diag["avg_chalk_index"] = float(np.mean(chalk_vals))
                        if penalty_pts:
                            pen_diag["avg_penalty_points"] = float(np.mean(penalty_pts))
                        pen_diag["applied"] = True
                _ep = diagnostics.get("ownership_penalty", {})
                _ep.update(pen_diag)
                diagnostics["ownership_penalty"] = _ep
        except Exception:
            # Non-fatal
            pass
        return lineups, diagnostics

    elif engine == "cp_sat_counts":
        print(
            f"🚀 Using CP-SAT Counts solver engine (PRP-14) (seed={seed}, site={site})"
        )
        try:
            from .solvers.cpsat_solver import solve_cpsat_iterative_counts
        except Exception as e:
            raise OptimizerError(
                code=ErrorCodes.CONFIG_ERROR,
                message=f"CP-SAT Counts engine unavailable: {e}",
                user_message="CP-SAT Counts engine is not available. Please install ortools or switch to CBC.",
                details={"import_error": str(e)},
            )

        lineups, diagnostics = solve_cpsat_iterative_counts(
            players, constraints, seed, site
        )
        # Merge DK ID diagnostics into solver diagnostics for consistency
        if not isinstance(diagnostics, dict):
            diagnostics = {}
        diagnostics.update(id_diagnostics)
        diagnostics.setdefault("engine", "cp_sat_counts")
        # Add ownership penalty diagnostics similar to CP-SAT
        try:
            pen_cfg = getattr(constraints, "ownership_penalty", None)
            if pen_cfg and pen_cfg.enabled:
                pen_diag: Dict[str, Any] = {
                    "enabled": True,
                    "mode": pen_cfg.mode,
                    "lambda_used": float(getattr(pen_cfg, "weight_lambda", 0.0) or 0.0),
                    "applied": False,
                    "reason": None,
                }
                any_own = any(p.get("own_proj") is not None for p in players)
                if not any_own:
                    pen_diag["applied"] = False
                    pen_diag["reason"] = "missing_or_invalid_own_proj"
                else:
                    lam = float(getattr(pen_cfg, "weight_lambda", 0.0) or 0.0)
                    if lam > 0 and lineups:
                        chalk_vals = []
                        penalty_pts = []
                        for lu in lineups:
                            gvals = []
                            for pl in lu.players:
                                if pl.own_proj is None:
                                    continue
                                own_pct = (
                                    pl.own_proj / 100.0
                                    if pl.own_proj > 1.0
                                    else float(pl.own_proj)
                                )
                                g = _g_curve_penalty(own_pct, pen_cfg)
                                gvals.append(g)
                            if gvals:
                                chalk_vals.append(float(np.mean(gvals)))
                                penalty_pts.append(float(lam * np.sum(gvals)))
                        if chalk_vals:
                            pen_diag["avg_chalk_index"] = float(np.mean(chalk_vals))
                        if penalty_pts:
                            pen_diag["avg_penalty_points"] = float(np.mean(penalty_pts))
                        pen_diag["applied"] = True
                _ep2 = diagnostics.get("ownership_penalty", {})
                _ep2.update(pen_diag)
                diagnostics["ownership_penalty"] = _ep2
        except Exception:
            pass
        return lineups, diagnostics

    # CBC (default) path
    print(f"🔧 Using CBC solver engine (seed={seed}, site={site})")

    # PRP-16: Handle ownership penalty "by_percent" mode
    ownership_penalty = constraints.ownership_penalty
    if (
        ownership_penalty
        and ownership_penalty.enabled
        and ownership_penalty.mode == "by_percent"
    ):

        print(
            f"🎯 Ownership penalty: by % off optimal (target: {ownership_penalty.target_offoptimal_pct:.1%})"
        )

        # Build projection map for off-optimal calculation
        proj_map = {p["player_id"]: p["proj"] for p in players}

        # Create build_and_solve function for lambda search
        def build_and_solve_fn(coeffs: Dict[str, float]) -> List[str]:
            # Build a temporary problem that uses the provided objective coefficients directly
            temp_problem, temp_var_index, temp_lp_variables, _ = build_problem(
                players, constraints, site, override_coeffs=coeffs
            )
            lineup_vars = solve_problem(
                temp_problem, temp_lp_variables, temp_var_index, seed
            )
            return [var_key[0] for var_key in lineup_vars] if lineup_vars else []

        # Find optimal lambda using bracket + bisection
        lam_used, achieved_pct, first_lineup_players = _find_lambda_by_percent(
            target_pct=ownership_penalty.target_offoptimal_pct,
            tol_pct=ownership_penalty.tol_offoptimal_pct,
            players=players,
            settings=ownership_penalty,
            build_and_solve_fn=build_and_solve_fn,
            proj_map=proj_map,
        )

        print(
            f"🎯 Lambda search result: λ={lam_used:.3f}, achieved {achieved_pct:.1%} off-optimal"
        )

        # Update penalty settings with found lambda for lineup generation
        ownership_penalty.weight_lambda = lam_used
        ownership_penalty.mode = "by_points"  # Switch to by_points for generation

    problem, var_index, lp_variables, base_objective = build_problem(
        players, constraints, site
    )

    # Generate lineups iteratively
    lineups: List[Lineup] = []
    for i in range(constraints.N_lineups):
        try:
            # Apply randomness for this iteration if user requested it, otherwise use base objective
            if constraints.randomness_pct > 0:
                apply_randomness_to_objective(
                    problem, lp_variables, var_index, constraints, seed + i
                )
            else:
                # Use base objective (no randomness when user sets 0%)
                problem.objective = base_objective

            lineup_vars = solve_problem(problem, lp_variables, var_index, seed)

            if not lineup_vars:
                # Infeasible - stop generating
                break

            lineup = convert_vars_to_lineup(lineup_vars, var_index, players, i + 1)
            lineups.append(lineup)

            # Add uniqueness constraint for next iteration
            if i < constraints.N_lineups - 1:
                add_uniqueness_constraint(
                    problem,
                    lp_variables,
                    lineup_vars,
                    constraints.unique_players,
                    f"Lineup_{i}_uniqueness",
                )

        except plp.PulpSolverError as e:
            if len(lineups) == 0:
                raise OptimizerError(
                    code=ErrorCodes.INFEASIBLE,
                    message=f"Solver failed: {str(e)}",
                    user_message="No valid lineups found. Try relaxing salary or team constraints.",
                    details={"solver_error": str(e), "generated_lineups": len(lineups)},
                )
            break

    if len(lineups) < constraints.N_lineups:
        # Partial generation - could be warning or info
        actual_count = len(lineups)
        if actual_count == 0:
            raise OptimizerError(
                code=ErrorCodes.INFEASIBLE,
                message="No feasible lineups found",
                user_message="No valid lineups found. Check salary limits and constraints.",
                details={"requested": constraints.N_lineups, "generated": 0},
            )

    # Build ownership penalty diagnostics (CBC)
    try:
        id_diagnostics.setdefault("engine", "cbc")
        pen_cfg = getattr(constraints, "ownership_penalty", None)
        if pen_cfg and pen_cfg.enabled:
            # Determine lambda used and percent-achieved if by_percent performed above
            lam_used = float(getattr(pen_cfg, "weight_lambda", 0.0) or 0.0)
            pen_diag: Dict[str, Any] = {
                "enabled": True,
                "mode": pen_cfg.mode,
                "lambda_used": lam_used,
                "applied": False,
                "reason": None,
            }
            # If by_percent flow was used earlier, try to infer achieved vs target from prints not available here;
            # we can recompute achieved for the first lineup
            try:
                if (
                    pen_cfg.mode == "by_points"
                    and "target_offoptimal_pct" in pen_cfg.__dict__
                ):
                    # no-op; legacy
                    pass
            except Exception:
                pass
            any_own = any(p.get("own_proj") is not None for p in players)
            if not any_own:
                pen_diag["applied"] = False
                pen_diag["reason"] = "missing_or_invalid_own_proj"
            else:
                # Compute averages over generated lineups
                if lam_used > 0 and lineups:
                    chalk_vals = []
                    penalty_pts = []
                    for lu in lineups:
                        gvals = []
                        for pl in lu.players:
                            if pl.own_proj is None:
                                continue
                            own_pct = (
                                pl.own_proj / 100.0
                                if pl.own_proj > 1.0
                                else float(pl.own_proj)
                            )
                            g = _g_curve_penalty(own_pct, pen_cfg)
                            gvals.append(g)
                        if gvals:
                            chalk_vals.append(float(np.mean(gvals)))
                            penalty_pts.append(float(lam_used * np.sum(gvals)))
                    if chalk_vals:
                        pen_diag["avg_chalk_index"] = float(np.mean(chalk_vals))
                    if penalty_pts:
                        pen_diag["avg_penalty_points"] = float(np.mean(penalty_pts))
                    pen_diag["applied"] = True
            # Optional debug info under DFS_DEBUG
            import os as _os

            if _os.environ.get("DFS_DEBUG"):
                try:
                    # Ownership snapshot: first 10 players
                    snap = []
                    for p in players[:10]:
                        own = p.get("own_proj")
                        if own is None:
                            continue
                        op = own / 100.0 if own > 1.0 else float(own)
                        gv = _g_curve_penalty(op, pen_cfg)
                        snap.append(
                            {
                                "name": p.get("name"),
                                "own_proj": float(op),
                                "g": float(gv),
                            }
                        )
                    # Objective sample from first lineup
                    obj_sample = None
                    if lineups:
                        lu0 = lineups[0]
                        proj_term = float(sum(pl.proj for pl in lu0.players))
                        gsum = 0.0
                        for pl in lu0.players:
                            if pl.own_proj is None:
                                continue
                            op = (
                                pl.own_proj / 100.0
                                if pl.own_proj > 1.0
                                else float(pl.own_proj)
                            )
                            gsum += float(_g_curve_penalty(op, pen_cfg))
                        penalty_term = float(lam_used * gsum)
                        obj_sample = {
                            "projection_term": proj_term,
                            "penalty_term": penalty_term,
                            "objective": proj_term - penalty_term,
                        }
                    pen_diag["debug"] = {
                        "weights_snapshot": snap,
                        "objective_sample": obj_sample,
                    }
                except Exception:
                    pass
            _ep3 = id_diagnostics.get("ownership_penalty", {})
            _ep3.update(pen_diag)
            id_diagnostics["ownership_penalty"] = _ep3
    except Exception:
        pass

    return lineups, id_diagnostics


def optimize_dk_strict(
    projections_path: str,
    constraints: Constraints,
    seed: int,
    player_ids_path: Optional[str] = None,
    engine: str = "cbc",
) -> Tuple[List[Lineup], Dict[str, Any]]:
    """
    DK-Strict optimizer using PRP-07 data loader

    This function enforces the PRP-07 contract:
    - Never use synthetic IDs
    - Only use repo-provided data from dk_data/
    - Fail fast if any player lacks a real DK ID

    Args:
        projections_path: Path to projections CSV (dk_data/projections.csv)
        constraints: Optimization constraints with DK-strict requirements
        seed: Random seed
        player_ids_path: Optional path to player IDs CSV (dk_data/player_ids.csv)

    Returns:
        Tuple of (lineups, diagnostics)

    Raises:
        RuntimeError: If any player lacks real DK ID (PRP-07 hard-fail contract)
        OptimizerError: For other optimization failures
    """
    try:
        # Load projections with DK-strict ID attachment
        projections_df = load_dk_strict_projections(projections_path, player_ids_path)

        # PRP-18.2: Normalize projections (ownership columns, etc.)
        projections_df, norm_info = _normalize_projections_df(projections_df)

        # Validate all players have real DK IDs
        validation = validate_dk_strict_data(projections_df)
        if not validation["is_valid"]:
            error_details = "; ".join(validation["errors"])
            raise RuntimeError(
                f"DK-strict validation failed: {error_details}. "
                f"All {validation['total_players']} players must have valid numeric DK IDs. "
                f"Update dk_data/player_ids.csv or projections with real DK IDs."
            )

        # Run optimizer with guaranteed DK IDs
        site: SiteType = "dk"  # PRP-07 is DK-specific
        lineups, diagnostics = optimize_with_diagnostics(
            projections_df, constraints, seed, site, None, engine
        )

        # Add DK-strict validation status to diagnostics
        diagnostics.update(
            {
                "dk_strict_mode": True,
                "dk_validation": validation,
                "data_source": f"DK-strict loader: {projections_path}",
            }
        )

        # PRP-18.2: Add normalization info to diagnostics for UI telemetry
        if norm_info and norm_info.get("ownership"):
            diagnostics.setdefault("normalization", {})["ownership"] = norm_info[
                "ownership"
            ]

        return lineups, diagnostics

    except RuntimeError as e:
        # Re-raise DK-strict failures directly
        raise e
    except Exception as e:
        # Wrap other errors as OptimizerError
        raise OptimizerError(
            code="DK_STRICT_FAILED",
            message=f"DK-strict optimization failed: {str(e)}",
            user_message=f"DK-strict mode failed: {str(e)}. Check dk_data/ files and try again.",
            details={
                "projections_path": projections_path,
                "player_ids_path": player_ids_path,
            },
        )


def optimize_to_dk_csv(
    projections_df: pd.DataFrame,
    constraints: Constraints,
    seed: int,
    player_ids_df: Optional[pd.DataFrame] = None,
) -> str:
    """
    Run the optimizer and return a DK-importable CSV string.

    Enforces the DK-Strict contract (PRP-06E):
    - Attaches real DK IDs (PRP-05) with validation and diagnostics
    - Converts lineups to a typed DataFrame
    - Validates lineups (all slots populated, IDs numeric, salary <= cap)
    - Exports exactly 8 DK IDs per lineup with header: PG,SG,SF,PF,C,G,F,UTIL

    Raises OptimizerError if validation fails or no valid lineups remain.
    """
    # Always run in DraftKings mode for this helper
    site: SiteType = "dk"  # type: ignore

    # Run optimizer with diagnostics and DK ID attachment
    lineups, id_diagnostics = optimize_with_diagnostics(
        projections_df, constraints, seed, site, player_ids_df
    )

    if not lineups:
        raise OptimizerError(
            code=ErrorCodes.INFEASIBLE,
            message="No lineups generated",
            user_message="No valid lineups found. Try relaxing constraints or increasing projection minimum.",
            details={
                "generated_lineups": 0,
                "id_match_rate": id_diagnostics.get("success_rate"),
            },
        )

    # Build typed DataFrame and validate against DK-Strict spec
    grid_df = lineups_to_grid_df(lineups, sport="nba", site=site)
    valid_df, errors = validate_grid_df(grid_df, sport="nba", site=site)

    if errors:
        # Summarize first few errors for the user
        preview = "; ".join(
            [
                f"Lineup {e.get('lineup_id')}: {', '.join(e.get('errors', [])[:2])}"
                for e in errors[:3]
            ]
        )
        raise OptimizerError(
            code="DK_STRICT_VALIDATION_FAILED",
            message=f"DK-Strict validation failed for {len(errors)} lineups",
            user_message=f"Cannot export DK CSV: {len(errors)} lineups failed validation. {preview}",
            details={"errors": errors},
        )

    # Export exactly the DK IDs in slot order
    return grid_df_to_dk_csv(valid_df, sport="nba", site=site)


def optimize_dk_strict_to_csv(
    projections_path: str,
    constraints: Constraints,
    seed: int,
    player_ids_path: Optional[str] = None,
    engine: str = "cbc",
) -> str:
    """
    DK-Strict optimization direct to CSV export

    This function implements the complete PRP-07 flow:
    1. Load projections with hard-fail DK ID validation
    2. Run optimization with DK-strict constraints
    3. Validate lineup grid against DK requirements
    4. Export exactly DK IDs in slot order

    Args:
        projections_path: Path to projections CSV (dk_data/projections.csv)
        constraints: Optimization constraints
        seed: Random seed
        player_ids_path: Optional path to player IDs CSV (dk_data/player_ids.csv)

    Returns:
        CSV string ready for DraftKings import

    Raises:
        RuntimeError: If any player lacks real DK ID (PRP-07 hard-fail)
        OptimizerError: If validation fails or no valid lineups
    """
    # Run DK-strict optimization
    lineups, diagnostics = optimize_dk_strict(
        projections_path, constraints, seed, player_ids_path, engine
    )

    if not lineups:
        raise OptimizerError(
            code=ErrorCodes.INFEASIBLE,
            message="No lineups generated in DK-strict mode",
            user_message="No valid lineups found. Check constraints and projections data.",
            details=diagnostics,
        )

    # Convert to grid DataFrame and validate
    grid_df = lineups_to_grid_df(lineups, sport="nba", site="dk")
    valid_df, errors = validate_grid_df(grid_df, sport="nba", site="dk")

    if errors:
        error_summary = "; ".join(
            [
                f"Lineup {e.get('lineup_id')}: {', '.join(e.get('errors', [])[:2])}"
                for e in errors[:3]
            ]
        )
        raise OptimizerError(
            code="DK_STRICT_VALIDATION_FAILED",
            message=f"DK-Strict validation failed for {len(errors)} lineups",
            user_message=f"Cannot export DK CSV: {len(errors)} lineups failed validation. {error_summary}",
            details={"errors": errors, "diagnostics": diagnostics},
        )

    # Export DK-compatible CSV
    return grid_df_to_dk_csv(valid_df, sport="nba", site="dk")


def validate_projections(df: pd.DataFrame, site: SiteType) -> None:
    """Validate projections DataFrame has required columns"""
    required_cols = ["name", "team", "position", "salary", "proj_fp"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise OptimizerError(
            code=ErrorCodes.MISSING_COLUMNS,
            message=f"Missing required columns: {missing_cols}",
            user_message=f"Required columns missing: {', '.join(missing_cols)}. Please check your projections data.",
            details={
                "missing_columns": missing_cols,
                "available_columns": list(df.columns),
            },
        )


def attach_player_ids_if_available(
    df: pd.DataFrame, site: SiteType, ids_df: Optional[pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Attach real DK player IDs when available, with comprehensive diagnostics

    Returns:
        Tuple of (updated_df, diagnostics_dict)
    """
    diagnostics = {
        "total_players": len(df),
        "matched_players": 0,
        "data_source": None,
        "errors": [],
        "warnings": [],
        "failed_name_matching": 0,
        "failed_position_validation": 0,
        "success_rate": 0.0,
    }

    if site != "dk":
        diagnostics["warnings"].append(f"Non-DK site ({site}) - skipping ID attachment")
        return df, diagnostics

    # If dk_id is already in the DataFrame, return as-is
    if "dk_id" in df.columns:
        existing_ids = df["dk_id"].notna().sum()
        diagnostics.update(
            {
                "matched_players": existing_ids,
                "success_rate": existing_ids / len(df) * 100,
                "data_source": "pre-existing_column",
                "warnings": ["DK IDs already present in projections data"],
            }
        )
        return df, diagnostics

    # Try provided IDs DF first; else load from disk
    ids = ids_df
    if ids is None:
        default_path = "dk_data/player_ids.csv"
        try:
            ids = pd.read_csv(default_path)
            diagnostics["data_source"] = default_path
        except FileNotFoundError:
            diagnostics["errors"].append(f"Player IDs file not found: {default_path}")
            return df, diagnostics
        except Exception as e:
            diagnostics["errors"].append(f"Error loading player IDs: {str(e)}")
            return df, diagnostics
    else:
        diagnostics["data_source"] = "provided_dataframe"

    # Validate required columns
    required_cols = ["ID", "Name", "TeamAbbrev", "Position"]
    missing_cols = [col for col in required_cols if col not in ids.columns]
    if missing_cols:
        diagnostics["errors"].append(
            f"Missing required columns in player IDs: {missing_cols}"
        )
        return df, diagnostics

    print(
        f"🔍 DK ID Matching: {len(df)} players in projections, {len(ids)} IDs available"
    )

    # Enhanced normalization for matching
    tmp = df.copy()
    tmp["__name_norm"] = tmp["name"].apply(normalize_player_name)
    tmp["__team_norm"] = (
        tmp["team"]
        .astype(str)
        .str.upper()
        .map(lambda t: TEAM_REPLACEMENT_DICT.get(t, t))
    )

    ids = ids.rename(
        columns={
            "ID": "dk_id",
            "Name": "name_ids",
            "TeamAbbrev": "team_ids",
            "Position": "pos_ids",
        }
    )
    ids["__name_norm"] = ids["name_ids"].apply(normalize_player_name)
    ids["__team_norm"] = (
        ids["team_ids"]
        .astype(str)
        .str.upper()
        .map(lambda t: TEAM_REPLACEMENT_DICT.get(t, t))
    )
    ids["__pos_list"] = ids["pos_ids"].astype(str).str.split("/")

    # Exact merge on normalized name + team
    merged = tmp.merge(
        ids[
            [
                "__name_norm",
                "__team_norm",
                "dk_id",
                "__pos_list",
                "name_ids",
                "team_ids",
            ]
        ],
        on=["__name_norm", "__team_norm"],
        how="left",
    )

    # Count initial exact matches
    initial_matches = merged["dk_id"].notna().sum()

    # Attempt fuzzy matching for remaining unmatched players
    if initial_matches < len(df) and FUZZY_MATCHING_AVAILABLE:
        fuzzy_matches = find_fuzzy_matches(merged, ids)

        if not fuzzy_matches.empty:
            # Apply fuzzy matches
            for _, match in fuzzy_matches.iterrows():
                idx = match["proj_index"]
                merged.at[idx, "dk_id"] = match["dk_id"]

            fuzzy_match_count = len(fuzzy_matches)
            initial_matches += fuzzy_match_count
            diagnostics["warnings"].append(
                f"Applied {fuzzy_match_count} fuzzy name matches"
            )

    diagnostics["failed_name_matching"] = len(df) - initial_matches

    # Validate position overlap
    def has_position_overlap(row):
        if pd.isna(row.get("dk_id")):
            return False
        proj_positions = [p.strip() for p in str(row["position"]).split("/")]
        id_positions = row["__pos_list"] if isinstance(row["__pos_list"], list) else []
        return any(p in id_positions for p in proj_positions)

    # Clear dk_id where positions don't overlap and track failures
    mask_bad_pos = merged["dk_id"].notna() & ~merged.apply(has_position_overlap, axis=1)
    position_failures = mask_bad_pos.sum()
    diagnostics["failed_position_validation"] = position_failures

    if position_failures > 0:
        failed_players = merged.loc[
            mask_bad_pos, ["name", "position", "name_ids", "pos_ids"]
        ].head(5)
        diagnostics["warnings"].append(
            f"Position validation failed for {position_failures} players"
        )
        for _, row in failed_players.iterrows():
            diagnostics["warnings"].append(
                f"  {row['name']} ({row['position']}) vs {row['name_ids']} ({row['pos_ids']})"
            )

    merged.loc[mask_bad_pos, "dk_id"] = pd.NA

    # Final match statistics
    final_matches = merged["dk_id"].notna().sum()
    diagnostics.update(
        {
            "matched_players": final_matches,
            "success_rate": final_matches / len(df) * 100,
        }
    )

    # Generate actionable guidance
    if final_matches == 0:
        diagnostics["errors"].append(
            "CRITICAL: Zero DK IDs matched - lineups will not be DK-compatible"
        )
        if diagnostics["failed_name_matching"] > 0:
            diagnostics["errors"].append(
                "• Check player name formatting in projections vs player_ids.csv"
            )
            diagnostics["errors"].append(
                "• Verify team abbreviations match between files"
            )
        if len(ids) == 0:
            diagnostics["errors"].append("• Player IDs file is empty")
    elif final_matches < len(df) * 0.95:  # Less than 95% match rate
        diagnostics["warnings"].append(
            f"Low match rate: {final_matches}/{len(df)} ({diagnostics['success_rate']:.1f}%)"
        )
        unmatched = merged[merged["dk_id"].isna()]["name"].head(10).tolist()
        diagnostics["warnings"].append(f"Unmatched players: {', '.join(unmatched[:5])}")

    # Log detailed results
    print(
        f"📊 Match Results: {final_matches}/{len(df)} ({diagnostics['success_rate']:.1f}%) successful"
    )
    if diagnostics["failed_name_matching"] > 0:
        print(
            f"❌ Name/Team matching failed: {diagnostics['failed_name_matching']} players"
        )
    if diagnostics["failed_position_validation"] > 0:
        print(
            f"⚠️  Position validation failed: {diagnostics['failed_position_validation']} players"
        )

    # Clean up temporary columns
    result_df = merged.drop(
        columns=["__name_norm", "__team_norm", "__pos_list", "name_ids", "team_ids"],
        errors="ignore",
    )
    return result_df, diagnostics


def convert_projections_to_players(df: pd.DataFrame, proj_min: float) -> List[Dict]:
    """Convert DataFrame to player dictionary format"""
    players = []

    for _, row in df.iterrows():
        if float(row["proj_fp"]) < proj_min:
            continue

        # Standardize team names
        team = row["team"].upper()
        if team in TEAM_REPLACEMENT_DICT:
            team = TEAM_REPLACEMENT_DICT[team]

        # Handle multi-position players (e.g., "PG/SG")
        positions = [pos.strip() for pos in str(row["position"]).split("/")]

        # Create stable player ID - prefer real IDs, with hash for collision avoidance
        name = str(row["name"])
        salary = int(str(row["salary"]).replace(",", ""))

        # Try to use existing player ID columns first, then generate stable ID
        dk_id = row.get("dk_id")
        if pd.notna(dk_id):
            player_id = str(int(float(dk_id)))
        else:
            player_id = (
                str(row.get("player_id", "")).strip()
                or str(row.get("fd_id", "")).strip()
                or f"{name}_{team}_{salary}_{hash(name) & 0xffff}"
            )

        # PRP-16: Handle ownership data - check both 'own%' and 'own_proj' columns
        own_proj = None
        if "own%" in row and pd.notna(row["own%"]):
            own_proj = float(row["own%"])
        elif "own_proj" in row and pd.notna(row["own_proj"]):
            own_proj = float(row["own_proj"])

        player = {
            "name": name,  # Keep original name for rule matching
            "team": team,
            "positions": positions,
            "salary": salary,
            "proj": float(row["proj_fp"]),
            "own_proj": own_proj,  # PRP-16: Ownership percentage for penalty calculation
            "stddev": float(row.get("stddev", 0)) if "stddev" in row else None,
            "minutes": float(row.get("minutes", 0)) if "minutes" in row else None,
            "player_id": player_id,  # Deterministic and collision-resistant ID
            "dk_id": (
                str(int(float(dk_id))) if pd.notna(dk_id) else None
            ),  # Real DK ID if available
        }

        players.append(player)

    return players


def build_problem(
    players: List[Dict],
    constraints: Constraints,
    site: SiteType,
    override_coeffs: Optional[Dict[str, float]] = None,
) -> Tuple[plp.LpProblem, Dict, Dict, plp.LpAffineExpression]:
    """
    Build optimization problem with stable variable ordering

    Returns:
        (problem, variable_index, lp_variables) tuple
    """
    problem = plp.LpProblem("NBA_Optimizer", plp.LpMaximize)

    # Create variables with stable ordering by (player_id, position)
    lp_variables = {}
    var_index = {}  # Maps variable tuple to player info

    # Sort players for deterministic ordering
    sorted_players = sorted(players, key=lambda p: (p["player_id"], p["name"]))

    for player in sorted_players:
        # Add eligible positions based on site
        eligible_positions = get_eligible_positions(player["positions"], site)

        for pos in eligible_positions:
            var_key = (player["player_id"], pos)
            # Sanitize player name to prevent solver issues with special characters
            safe_name = re.sub(r"[^A-Za-z0-9_]", "_", player["name"])
            var_name = f"{safe_name}_{pos}_{player['player_id'][:8]}"

            lp_variables[var_key] = plp.LpVariable(name=var_name, cat=plp.LpBinary)
            var_index[var_key] = player

    # Set objective - maximize projected points (with ownership penalty support)
    ownership_penalty = constraints.ownership_penalty

    if override_coeffs is not None:
        # Directly use provided coefficients (typically used during λ search)
        objective_terms = []
        for var_key, variable in lp_variables.items():
            pid = var_index[var_key]["player_id"]
            coeff = override_coeffs.get(pid, var_index[var_key]["proj"])
            objective_terms.append(coeff * variable)
        base_objective = plp.lpSum(objective_terms)
    elif (
        ownership_penalty
        and ownership_penalty.enabled
        and ownership_penalty.mode == "by_points"
        and ownership_penalty.weight_lambda > 0
    ):
        # Apply ownership penalty in "by_points" mode
        penalty_terms = []
        for var_key, variable in lp_variables.items():
            player = var_index[var_key]
            base_proj = player["proj"]
            if player.get("own_proj") is not None:
                own_pct = (
                    player["own_proj"] / 100.0
                    if player["own_proj"] > 1.0
                    else player["own_proj"]
                )
                penalty = ownership_penalty.weight_lambda * _g_curve_penalty(
                    own_pct, ownership_penalty
                )
                effective_proj = base_proj - penalty
            else:
                effective_proj = base_proj
            penalty_terms.append(effective_proj * variable)
        base_objective = plp.lpSum(penalty_terms)
    else:
        # Standard objective without penalty
        base_objective_terms = [
            var_index[var_key]["proj"] * variable
            for var_key, variable in lp_variables.items()
        ]
        base_objective = plp.lpSum(base_objective_terms)

    problem.objective = base_objective

    # Add constraints
    add_salary_constraints(problem, lp_variables, var_index, constraints, site)
    add_position_constraints(problem, lp_variables, var_index, site)
    add_team_constraints(problem, lp_variables, var_index, constraints, site)
    add_player_constraints(problem, lp_variables, var_index, constraints)

    return problem, var_index, lp_variables, base_objective


def apply_randomness_to_objective(
    problem: plp.LpProblem,
    lp_variables: Dict,
    var_index: Dict,
    constraints: Constraints,
    iteration_seed: int,
):
    """Apply randomness to the objective function for lineup diversity"""
    # Set seed for this specific iteration
    np.random.seed(iteration_seed)

    # Create new randomized objective
    objective_terms = []
    ownership_penalty = constraints.ownership_penalty
    use_penalty = (
        ownership_penalty
        and ownership_penalty.enabled
        and ownership_penalty.mode == "by_points"
        and ownership_penalty.weight_lambda > 0
    )
    for var_key, variable in lp_variables.items():
        player = var_index[var_key]
        if player.get("stddev") and constraints.randomness_pct > 0:
            randomized_proj = np.random.normal(
                player["proj"], player["stddev"] * constraints.randomness_pct / 100
            )
        else:
            randomized_proj = player["proj"]
        # subtract ownership penalty if applicable
        if use_penalty and player.get("own_proj") is not None:
            own_pct = (
                player["own_proj"] / 100.0
                if player["own_proj"] > 1.0
                else player["own_proj"]
            )
            penalty = ownership_penalty.weight_lambda * _g_curve_penalty(
                own_pct, ownership_penalty
            )
            effective_proj = randomized_proj - penalty
        else:
            effective_proj = randomized_proj
        objective_terms.append(effective_proj * variable)

    problem.objective = plp.lpSum(objective_terms)


def get_eligible_positions(player_positions: List[str], site: SiteType) -> List[str]:
    """Get all eligible lineup positions for a player in deterministic order"""
    # Always return positions in the same order for deterministic variable creation
    base = [pos for pos in ["PG", "SG", "SF", "PF", "C"] if pos in player_positions]

    if site == "dk":
        # DraftKings position eligibility - add in fixed order
        if any(pos in ("PG", "SG") for pos in base):
            base.append("G")
        if any(pos in ("SF", "PF") for pos in base):
            base.append("F")
        base.append("UTIL")  # All players eligible for UTIL

    return base


def add_salary_constraints(
    problem: plp.LpProblem,
    lp_variables: Dict,
    var_index: Dict,
    constraints: Constraints,
    site: SiteType,
):
    """Add salary constraints"""
    salary_sum = plp.lpSum(
        var_index[var_key]["salary"] * variable
        for var_key, variable in lp_variables.items()
    )

    # Max salary constraint
    max_sal = constraints.max_salary or (50000 if site == "dk" else 60000)
    problem += salary_sum <= max_sal, "Max_Salary"

    # Min salary constraint - only if explicitly provided (avoid tight defaults)
    if constraints.min_salary is not None:
        problem += salary_sum >= constraints.min_salary, "Min_Salary"


def add_position_constraints(
    problem: plp.LpProblem, lp_variables: Dict, var_index: Dict, site: SiteType
):
    """Add position-specific constraints"""
    if site == "dk":
        # DraftKings: PG, SG, SF, PF, C, G, F, UTIL
        positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        for pos in positions:
            position_sum = plp.lpSum(
                variable
                for var_key, variable in lp_variables.items()
                if var_key[1] == pos
            )
            problem += position_sum == 1, f"Position_{pos}"

    else:  # FanDuel
        # FanDuel: 2 each of PG, SG, SF, PF + 1 C
        for pos in ["PG", "SG", "SF", "PF"]:
            position_sum = plp.lpSum(
                variable
                for var_key, variable in lp_variables.items()
                if var_key[1] == pos
            )
            problem += position_sum == 2, f"Position_{pos}"

        # Center constraint
        center_sum = plp.lpSum(
            variable for var_key, variable in lp_variables.items() if var_key[1] == "C"
        )
        problem += center_sum == 1, "Position_C"

    # Each player can only be selected once
    player_sums = {}
    for var_key, variable in lp_variables.items():
        player_id = var_key[0]
        if player_id not in player_sums:
            player_sums[player_id] = []
        player_sums[player_id].append(variable)

    for player_id, variables in player_sums.items():
        problem += plp.lpSum(variables) <= 1, f"Player_{player_id}_once"


def add_team_constraints(
    problem: plp.LpProblem,
    lp_variables: Dict,
    var_index: Dict,
    constraints: Constraints,
    site: SiteType,
):
    """Add team-based constraints"""
    # Team limits
    teams = set(player["team"] for player in var_index.values())

    for team in teams:
        team_variables = [
            variable
            for var_key, variable in lp_variables.items()
            if var_index[var_key]["team"] == team
        ]

        # Specific team limits
        if team in constraints.team_limits:
            limit = constraints.team_limits[team]
            problem += plp.lpSum(team_variables) <= limit, f"Team_{team}_limit_{limit}"

        # Global team limit - default to 4 for DK if not specified
        global_limit = constraints.global_team_limit
        if global_limit is None and site == "dk":
            global_limit = 4  # DK convention

        if global_limit is not None:
            # Skip for FanDuel if global limit >= 4 (their max is 4 anyway)
            if not (site == "fd" and global_limit >= 4):
                problem += (
                    plp.lpSum(team_variables) <= global_limit,
                    f"Team_{team}_global_{global_limit}",
                )


def add_player_constraints(
    problem: plp.LpProblem,
    lp_variables: Dict,
    var_index: Dict,
    constraints: Constraints,
):
    """Add at_least and at_most player constraints"""
    # At least constraints
    for rule in constraints.at_least:
        matching_variables = [
            variable
            for var_key, variable in lp_variables.items()
            if var_index[var_key]["name"] in rule.players
        ]
        if matching_variables:
            problem += (
                plp.lpSum(matching_variables) >= rule.count,
                f"AtLeast_{rule.count}_{hash(tuple(rule.players))}",
            )

    # At most constraints
    for rule in constraints.at_most:
        matching_variables = [
            variable
            for var_key, variable in lp_variables.items()
            if var_index[var_key]["name"] in rule.players
        ]
        if matching_variables:
            problem += (
                plp.lpSum(matching_variables) <= rule.count,
                f"AtMost_{rule.count}_{hash(tuple(rule.players))}",
            )


def solve_problem(
    problem: plp.LpProblem, lp_variables: Dict, var_index: Dict, seed: int
) -> Optional[List[Tuple]]:
    """
    Solve optimization problem with CBC solver configuration

    Returns:
        List of selected variable keys or None if infeasible
    """
    try:
        # Use CBC solver with random seed for deterministic tie-breaking
        solver = plp.PULP_CBC_CMD(
            msg=False, timeLimit=9, options=[f"randomSeed {seed}"]
        )
        problem.solve(solver)

        if plp.LpStatus[problem.status] != "Optimal":
            return None

        # Get selected variables using our variable tracking
        selected_vars = []
        for var_key, variable in lp_variables.items():
            if variable.varValue and variable.varValue > 0.5:
                selected_vars.append(var_key)  # var_key is (player_id, pos)

        return selected_vars

    except Exception as e:
        raise OptimizerError(
            code=ErrorCodes.SOLVER_TIMEOUT,
            message=f"Solver error: {str(e)}",
            user_message="Optimization failed. Try reducing lineup count or relaxing constraints.",
            details={"solver_error": str(e)},
        )


def convert_vars_to_lineup(
    var_keys: List[Tuple], var_index: Dict, players: List[Dict], lineup_id: int
) -> Lineup:
    """Convert selected variables to Lineup object"""
    lineup_players = []
    total_salary = 0
    total_proj = 0

    for player_id, pos in var_keys:
        var_key = (player_id, pos)
        if var_key in var_index:
            player_data = var_index[var_key]

            player = Player(
                player_id=player_data["player_id"],
                name=player_data["name"],
                pos=pos,
                team=player_data["team"],
                salary=player_data["salary"],
                proj=player_data["proj"],
                dk_id=player_data.get("dk_id"),
                own_proj=player_data.get("own_proj"),
                stddev=player_data.get("stddev"),
                minutes=player_data.get("minutes"),
            )

            lineup_players.append(player)
            total_salary += player.salary
            total_proj += player.proj

    return Lineup(
        lineup_id=lineup_id,
        total_proj=round(total_proj, 2),
        total_salary=total_salary,
        players=lineup_players,
    )


def add_uniqueness_constraint(
    problem: plp.LpProblem,
    lp_variables: Dict,
    selected_vars: List[Tuple],
    unique_count: int,
    constraint_name: str,
):
    """Add constraint to ensure lineup uniqueness at the player level"""
    # Only skip if unique_count is 0 or negative (no uniqueness required)
    if unique_count <= 0:
        return

    # Get unique player IDs from the selected lineup
    selected_player_ids = {var_key[0] for var_key in selected_vars}

    # For each player in the previous lineup, find ALL their position variables
    # This prevents selecting the same player in any position
    player_vars = [
        variable
        for var_key, variable in lp_variables.items()
        if var_key[0] in selected_player_ids
    ]

    if player_vars:
        # Must have at least unique_count different players
        problem += (
            plp.lpSum(player_vars) <= len(selected_player_ids) - unique_count,
            constraint_name,
        )


# Legacy class wrapper for backward compatibility
class NBA_Optimizer:
    """Legacy class wrapper - use optimize() function instead"""

    def __init__(self, site=None, num_lineups=0, num_uniques=1):
        self.site = site
        self.num_lineups = num_lineups
        self.num_uniques = num_uniques
        print(
            "Warning: NBA_Optimizer class is deprecated. Use optimize() function instead."
        )

    # PRP-Ownership-Normalization: Pre-solve guards, export exact solver inputs, and run_id
    try:
        # Generate run id and attach to diagnostics
        RUN_ID = str(int(time.time()))

        def _df_hash(df: pd.DataFrame) -> str:
            try:
                return hashlib.sha256(
                    pd.util.hash_pandas_object(df, index=True).values
                ).hexdigest()
            except Exception:
                return uuid.uuid4().hex

        id_diagnostics.setdefault("normalization", {}).setdefault("ownership", {})[
            "run_id"
        ] = RUN_ID

        # Required columns just before solve (pre-contract)
        required = {"name", "team", "position", "salary", "proj_fp"}
        missing = required - set(projections_df.columns)
        if missing:
            raise OptimizerError(
                code=ErrorCodes.MISSING_COLUMNS,
                message=f"Missing columns pre-solve: {missing}",
                user_message=f"Required columns missing pre-solve: {', '.join(sorted(missing))}",
                details={"missing": sorted(list(missing))},
            )

        # Normalization guard only if user enabled ownership penalty
        try:
            pen_cfg = getattr(constraints, "ownership_penalty", None)
            if pen_cfg and getattr(pen_cfg, "enabled", False):
                mx = (
                    float(projections_df["own_proj"].max())
                    if "own_proj" in projections_df.columns
                    else float("inf")
                )
                id_diagnostics["normalization"]["ownership"][
                    "own_proj_max_pre_solve"
                ] = mx
                assert mx <= 1.000001, f"own_proj not normalized (max={mx})"
        except Exception as _e:
            # If assertion fails, raise as OptimizerError to surface cleanly
            raise OptimizerError(
                code=ErrorCodes.INVALID_PROJECTIONS,
                message=str(_e),
                user_message="Ownership column appears non-normalized. Ensure own_proj is on [0,1] scale.",
                details={"max": mx if "mx" in locals() else None},
            )

        # Solver Input Contract: export exact solver inputs and manifest
        try:
            df_contract = projections_df.copy()
            # Canonicalize FPts column for export/contract
            rename_map = {
                "FPTS": "FPts",
                "fpts": "FPts",
                "proj": "FPts",
                "projection": "FPts",
                "Projection": "FPts",
            }
            df_contract = df_contract.rename(
                columns={
                    k: v for k, v in rename_map.items() if k in df_contract.columns
                }
            )
            if "FPts" not in df_contract.columns and "proj_fp" in df_contract.columns:
                df_contract["FPts"] = df_contract["proj_fp"]
            # Ensure player_id column exists for contract hashing
            if "player_id" not in df_contract.columns:
                # Prefer dk_id when present, otherwise synthesize stable-ish ID similar to convert_projections_to_players
                def _mk_pid(row):
                    dkid = row.get("dk_id")
                    if pd.notna(dkid):
                        try:
                            return str(int(float(dkid)))
                        except Exception:
                            return str(dkid)
                    name = str(row.get("name", "")).strip()
                    team = str(row.get("team", "")).strip().upper()
                    salary = row.get("salary")
                    try:
                        salary = int(str(salary).replace(",", ""))
                    except Exception:
                        salary = str(salary)
                    return f"{name}_{team}_{salary}_{hash(name) & 0xffff}"

                df_contract["player_id"] = df_contract.apply(_mk_pid, axis=1)

            # Contract required columns
            contract_required = {
                "player_id",
                "name",
                "team",
                "position",
                "salary",
                "FPts",
                "own_proj",
            }
            miss2 = contract_required - set(df_contract.columns)
            assert not miss2, f"[CONTRACT] Missing columns pre-solve: {miss2}"
            # Ownership must be in [0,1]
            mx = (
                float(df_contract["own_proj"].max())
                if "own_proj" in df_contract.columns
                else float("inf")
            )
            assert mx <= 1.000001, f"[CONTRACT] own_proj not normalized (max={mx})"
            # Contract hash over deterministic subset
            cols_for_hash = [
                "player_id",
                "FPts",
                "own_proj",
                "salary",
                "team",
                "position",
            ]
            key = (
                df_contract[cols_for_hash].sort_values("player_id").to_csv(index=False)
            )
            contract_hash = hashlib.sha256(key.encode()).hexdigest()

            # Build manifest (always available in diagnostics)
            manifest = {
                "run_id": RUN_ID,
                "contract_hash": contract_hash,
                "rows": int(df_contract.shape[0]),
                "cols": sorted(df_contract.columns.tolist()),
                "own_proj_max": mx,
                "note": "This CSV is the exact DataFrame passed into the solver.",
            }

            # Diagnostics (include CSV content in-memory so UI can write single-location export)
            id_diagnostics.setdefault("solver_contract", {})["run_id"] = RUN_ID
            id_diagnostics["solver_contract"]["contract_hash"] = contract_hash
            try:
                id_diagnostics["solver_contract"]["csv"] = df_contract.to_csv(
                    index=False
                )
                id_diagnostics["solver_contract"]["manifest"] = manifest
            except Exception:
                pass

            # Optional: write artifacts to disk if explicitly enabled
            try:
                if os.environ.get("DFS_WRITE_CONTRACT_ARTIFACTS", "0") in (
                    "1",
                    "true",
                    "True",
                ):
                    out_dir = os.path.join("artifacts", f"run_{RUN_ID}")
                    os.makedirs(out_dir, exist_ok=True)
                    solver_csv = os.path.join(out_dir, "solver_inputs.csv")
                    df_contract.to_csv(solver_csv, index=False)
                    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
                        import json as _json

                        _json.dump(manifest, f, indent=2)
                    id_diagnostics["solver_contract"]["solver_inputs_path"] = solver_csv
            except Exception:
                pass
            # Backcompat fields used by UI pre-PRP
            id_diagnostics.setdefault("normalization", {}).setdefault("ownership", {})[
                "projections_used_hash"
            ] = _df_hash(df_contract)
            print(
                f"[CONTRACT] run={RUN_ID} rows={df_contract.shape[0]} own_max={mx:.3f} hash={contract_hash[:12]}"
            )
        except AssertionError as _ae:
            # Surface contract failures clearly
            id_diagnostics.setdefault("solver_contract", {})
            id_diagnostics["solver_contract"]["error"] = str(_ae)
            print(f"[CONTRACT][ERROR] {str(_ae)}")
            raise OptimizerError(
                code=ErrorCodes.INVALID_PROJECTIONS,
                message=str(_ae),
                user_message="Solver input contract failed: missing columns or non-normalized ownership.",
                details={"error": str(_ae)},
            )
        except Exception as _ue:
            # Do not silently swallow unexpected issues; attach to diagnostics and log
            try:
                id_diagnostics.setdefault("solver_contract", {})
                id_diagnostics["solver_contract"]["error"] = str(_ue)
                print(f"[CONTRACT][UNEXPECTED] {str(_ue)}")
            except Exception:
                pass
    except OptimizerError:
        raise
    except Exception:
        pass
