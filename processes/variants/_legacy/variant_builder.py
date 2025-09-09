# Variant Builder (auto-generated from scaffold in orchestration task)
from __future__ import annotations
import json, csv, random, os, sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Iterable, Tuple
from src.utils.column_mapper import (
    suggest_auto_mapping,
    INTERNAL_FIELDS,
    validate_mapping,
    normalize_header,
)
import pandas as pd
from typing import Any

from src.config import paths


# ---------- Data models ----------
@dataclass(frozen=True)
class Player:
    id: str
    pos: str  # Primary position (for backward compatibility)
    positions: List[str]  # All eligible positions
    team: str
    salary: int
    proj: float
    ceil: float
    own: float
    archetype: str = ""


@dataclass
class Config:
    variants_per_base: int = 5
    min_uniques: int = 2
    global_min_distance: int = 2
    projection_delta: float = 3.0
    max_total_own: float = 160.0
    salary_buckets: Tuple[Tuple[int, int], ...] = (
        (49500, 50000),
        (49000, 49499),
        (0, 48999),
    )
    salary_mix: Tuple[float, ...] = (0.45, 0.35, 0.20)
    random_seed: int = 23
    # Advanced
    relative_salary_window: int = 700  # lo = max(48000, base_salary - window)
    ceil_toggle_k: int = 3  # use ceiling metric every k-th variant (k>0)


# SLOTS and DK salary constraints
SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
POS_TO_SLOTS = {
    "PG": ["PG", "G", "UTIL"],
    "SG": ["SG", "G", "UTIL"],
    "SF": ["SF", "F", "UTIL"],
    "PF": ["PF", "F", "UTIL"],
    "C": ["C", "UTIL"],
}
# DK constraints
DK_SAL_LO = 48000
DK_SAL_HI = 50000
# ORB schema column order
ORB_ORDER = ["player_id", "name", "team", "pos", "salary", "proj", "ceil", "own"]
_rng = random.Random()


# ---- Debug logging ----
def _debug_enabled() -> bool:
    try:
        v = os.getenv("DEBUG_VARIANTS", "").strip().lower()
        return v in {"1", "true", "yes", "on"}
    except Exception:
        return False


from typing import TextIO


def _dprint(
    *args: object,
    sep: str | None = " ",
    end: str | None = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    if _debug_enabled():
        if file is None:
            file = sys.stderr
        print("[VB]", *args, sep=sep, end=end, file=file, flush=flush)


# ---- Numeric coercion helpers (solve Pylance Scalar -> int/float) ----
def _as_int(x: Any) -> int:
    try:
        if isinstance(x, (bytes, bytearray, memoryview)):
            x = x.decode() if isinstance(x, (bytes, bytearray)) else x.tobytes().decode()
        if isinstance(x, str):
            s = x
            # strip currency, commas, etc.
            s = "".join(ch for ch in s if ch.isdigit() or ch in {"-", "."})
            if s in {"", "-", "."}:
                return 0
            return int(float(s))
        return int(float(x))
    except Exception:
        return 0


def _as_float(x: Any) -> float:
    try:
        if isinstance(x, (bytes, bytearray, memoryview)):
            x = x.decode() if isinstance(x, (bytes, bytearray)) else x.tobytes().decode()
        if isinstance(x, str):
            s = x.replace("%", "").replace(",", "").strip()
            if s.lower() in {"", ".", "-", "nan", "none"}:
                return 0.0
            return float(s)
        return float(x)
    except Exception:
        return 0.0


# ---------- IO ----------


# Helper for normalizing pool DataFrame using column_mapper
def _normalize_pool_with_mapper(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Use column_mapper to normalize any incoming projections/pool DataFrame into
    the canonical columns needed for Player: player_id,name,team,pos,pos2,salary,proj_fp,ceiling,own_proj.
    Returns a DataFrame with columns: player_id,name,team,pos,salary,proj,ceil,own
    """
    # Get auto suggestions from aliases
    mapping = suggest_auto_mapping(df)
    errs = validate_mapping(mapping, INTERNAL_FIELDS)

    # Required fields for robust operation
    req = ["name", "team", "position", "salary", "proj_fp"]
    missing = [f for f in req if mapping.get(f, "—") == "—"]
    if missing:
        raise ValueError(
            f"Column mapping failed: missing required fields {missing}. Found columns={list(df.columns)}; mapping={mapping}"
        )

    # Utility to pull a source column if mapped
    def col(field, default_series=None):
        src = mapping.get(field)
        if src and src in df.columns:
            return df[src]
        return default_series if default_series is not None else pd.Series([None] * len(df))

    norm = pd.DataFrame(
        {
            "player_id": col("player_id", default_series=pd.Series([""] * len(df))).astype(str),
            "name": col("name").astype(str),
            "team": col("team").astype(str),
            "pos": col("position").astype(str),
            "pos2": col("pos2", default_series=pd.Series([""] * len(df))).astype(str),
            "salary": col("salary"),
            "proj": col("proj_fp"),
            "ceil": col("ceiling"),
            "own": col("own_proj"),
        }
    )

    # Normalize salary → int
    norm["salary"] = (
        norm["salary"]
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
        .replace("", "0")
        .astype(int)
    )

    # Proj/ceil → float; ceil fallback to proj
    norm["proj"] = pd.to_numeric(norm["proj"], errors="coerce").fillna(0.0)
    norm["ceil"] = pd.to_numeric(norm["ceil"], errors="coerce")
    norm["ceil"] = norm["ceil"].fillna(norm["proj"])

    # Ownership: accept % or decimal, clamp to 0–100
    own = pd.to_numeric(norm["own"], errors="coerce")
    frac_mask = own.notna() & (own <= 1.0)
    own.loc[frac_mask] = own.loc[frac_mask] * 100.0
    norm["own"] = own.fillna(0.0).clip(0.0, 100.0)

    # Merge positions: pos + pos2 ⇒ "PG/SG" form
    def merge_pos(p1, p2):
        s = (p1 or "").replace("|", "/").replace(",", "/").replace(" ", "")
        if "/" in s or not p2:
            return s or "UTIL"
        s2 = (p2 or "").replace("|", "/").replace(",", "/").replace(" ", "")
        if s2 and s2 not in s:
            return f"{s}/{s2}" if s else s2
        return s or "UTIL"

    norm["pos"] = [merge_pos(a, b) for a, b in zip(norm["pos"], norm["pos2"])]

    return norm[["player_id", "name", "team", "pos", "salary", "proj", "ceil", "own"]]


# New implementation of _read_player_pool
def _read_player_pool(path: str) -> Dict[str, Player]:
    """
    Read player pool from CSV and return {player_id: Player}.
    If the file already matches the ORB schema (player_pool.csv), normalize types and use it.
    Otherwise, use the column_mapper to adapt arbitrary projections CSVs to the canonical schema.
    """
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(path, engine="python")

    # Fast path: ORB schema already present
    orb_cols = {"player_id", "name", "team", "pos", "salary", "proj", "ceil", "own"}
    if orb_cols.issubset(set(df.columns)):
        norm = df[ORB_ORDER].copy()
        # Ensure types / normalization
        norm["salary"] = (
            norm["salary"]
            .astype(str)
            .str.replace(r"[^0-9]", "", regex=True)
            .replace("", "0")
            .astype(int)
        )
        norm["proj"] = pd.to_numeric(norm["proj"], errors="coerce").fillna(0.0)
        norm["ceil"] = pd.to_numeric(norm["ceil"], errors="coerce").fillna(norm["proj"])
        own = pd.to_numeric(norm["own"], errors="coerce")
        frac = own.notna() & (own <= 1.0)
        own.loc[frac] = own.loc[frac] * 100.0
        norm["own"] = own.fillna(0.0).clip(0.0, 100.0)
        norm["pos"] = (
            norm["pos"]
            .astype(str)
            .str.replace("|", "/", regex=False)
            .str.replace(",", "/", regex=False)
            .str.replace(" ", "", regex=False)
        )
    else:
        # Use the mapper to normalize unknown schemas
        norm = _normalize_pool_with_mapper(df)

    # Attempt to attach canonical DK IDs (8-digit) from dk_data/player_ids.csv
    try:
        ids_path = Path("dk_data/player_ids.csv")
        if ids_path.exists():
            ids_df = pd.read_csv(ids_path, engine="python")
            # Flexible column resolution
            lower = {c.lower(): c for c in ids_df.columns}
            id_col = lower.get("id") or lower.get("dk_id") or lower.get("player_id")
            name_col = lower.get("name") or lower.get("player") or lower.get("playername")
            team_col = lower.get("teamabbrev") or lower.get("team") or lower.get("tm")
            if id_col and name_col and team_col:
                ids_sub = ids_df[[id_col, name_col, team_col]].copy()
                ids_sub.columns = ["dk_id", "name_ids", "team_ids"]
                ids_sub["__name_norm"] = ids_sub["name_ids"].astype(str).str.strip().str.lower()
                ids_sub["__team_norm"] = ids_sub["team_ids"].astype(str).str.strip().str.upper()

                norm["__name_norm"] = norm["name"].astype(str).str.strip().str.lower()
                norm["__team_norm"] = norm["team"].astype(str).str.strip().str.upper()

                # Standardize common team variants
                for col in ("__team_norm",):
                    norm[col] = norm[col].replace(
                        {
                            "PHO": "PHX",
                            "GS": "GSW",
                            "SA": "SAS",
                            "NO": "NOP",
                            "NY": "NYK",
                        }
                    )
                    ids_sub[col] = ids_sub[col].replace(
                        {
                            "PHO": "PHX",
                            "GS": "GSW",
                            "SA": "SAS",
                            "NO": "NOP",
                            "NY": "NYK",
                        }
                    )

                norm = norm.merge(
                    ids_sub[["__name_norm", "__team_norm", "dk_id"]],
                    on=["__name_norm", "__team_norm"],
                    how="left",
                )
                # Prefer canonical 8-digit dk_id when present
                norm["dk_id"] = norm["dk_id"].astype(str)
            # Clean helpers if merge didn't happen
            norm = norm.drop(columns=["__name_norm", "__team_norm"], errors="ignore")
    except Exception:
        # Best-effort only; continue without external IDs
        pass

    out: Dict[str, Player] = {}
    n_single_pos = 0
    n_multi_pos = 0
    n_sal0 = 0
    n_proj0 = 0
    n_ceil_eq_proj = 0
    n_own_le1 = 0
    for _, row in norm.iterrows():
        pid = str(row.get("player_id", "")).strip()
        # Prefer canonical dk_id if present and shaped correctly (8 digits)
        dkid = str(row.get("dk_id", "")).strip() if "dk_id" in norm.columns else ""
        if dkid.isdigit() and len(dkid) == 8:
            pid = dkid
        # Else fallback to existing 8-digit player_id if valid
        if not (pid.isdigit() and len(pid) == 8):
            # As last resort, derive from name+team+salary (stable)
            try:
                sal_i = int(row["salary"]) if pd.notna(row["salary"]) else 0
            except Exception:
                sal_i = 0
            pid = f"{row['name']}_{row['team']}_{sal_i}"
        positions = [p for p in str(row["pos"]).split("/") if p]
        if not positions:
            positions = ["UTIL"]
        pl = Player(
            id=pid,
            pos=positions[0],
            positions=positions,
            team=str(row["team"]),
            salary=_as_int(row["salary"]),
            proj=_as_float(row["proj"]),
            ceil=(_as_float(row["ceil"]) if pd.notna(row["ceil"]) else _as_float(row["proj"])),
            own=_as_float(row["own"]),
        )
        out[pid] = pl

        # Add robust alias keys for mapping base lineup IDs (prefix and name+team)
        alias_nts = f"{row['name']}_{row['team']}_{int(_as_int(row['salary']))}"
        alias_nt = f"{row['name']}_{row['team']}"
        out.setdefault(alias_nts, pl)
        out.setdefault(alias_nt, pl)

        # Stats for diagnostics
        if len(positions) == 1:
            n_single_pos += 1
        else:
            n_multi_pos += 1
        if _as_int(row["salary"]) == 0:
            n_sal0 += 1
        if _as_float(row["proj"]) == 0.0:
            n_proj0 += 1
        if _as_float(row["ceil"]) == _as_float(row["proj"]):
            n_ceil_eq_proj += 1
        if _as_float(row["own"]) <= 1.0:
            n_own_le1 += 1

    # Debug diagnostics (guarded)
    if _debug_enabled():
        n = len(out)
        denom = max(1, len(norm))
        _dprint(
            "pool stats",
            {
                "players": n,
                "pct_salary0": round(100.0 * n_sal0 / denom, 2),
                "pct_proj0": round(100.0 * n_proj0 / denom, 2),
                "pct_ceil_eq_proj": round(100.0 * n_ceil_eq_proj / denom, 2),
                "pct_own_le1": round(100.0 * n_own_le1 / denom, 2),
                "multi_pos": n_multi_pos,
                "single_pos": n_single_pos,
            },
        )

    return out


def _read_lineups_long(path: str) -> List[List[str]]:
    """Read lineups from either long format or DK optimizer wide format"""
    import re

    p = Path(path)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
        # Expect long format: lineup_id, slot, player_id
        need = {"lineup_id", "player_id"}
        if not need.issubset(df.columns):
            return []
        bucket = defaultdict(list)
        for _, row in df.iterrows():
            bucket[str(row["lineup_id"])].append(str(row["player_id"]))
        return [sorted(pids) for _, pids in sorted(bucket.items())]
    else:
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            first_row = next(r, None)
            if not first_row:
                return []

            # Reset reader
            f.seek(0)
            r = csv.DictReader(f)

            # Check format: if has 'lineup_id' it's long format, otherwise DK wide format
            if "lineup_id" in first_row:
                # Long format
                bucket = defaultdict(list)
                for row in r:
                    bucket[row["lineup_id"]].append(row["player_id"])
                return [sorted(pids) for _, pids in sorted(bucket.items())]
            else:
                # DK wide format: PG,SG,SF,PF,C,G,F,UTIL columns with display strings
                # Stop reusing embedded numeric IDs; parse name/team and emit synthetic keys "Name_TEAM"
                lineups = []
                positions = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]

                def parse_key(cell: str) -> str | None:
                    if not cell:
                        return None
                    s = str(cell).strip()
                    # Handle PRP-26 safe format: "Name (salary) • TEAM • dk_id"
                    if "•" in s:
                        parts = [p.strip() for p in s.split("•")]
                        if len(parts) >= 2:
                            left = parts[0]
                            team = parts[1].split()[0].upper()
                            name = left.split("(")[0].strip()
                            if name and team:
                                return f"{name}_{team}"
                    # Handle legacy "Name (12345 TEAM)" or "Name (TEAM)"
                    m = re.match(r"^(.*?)\((?:\d+\s+)?([A-Z]{2,4})\)$", s)
                    if m:
                        name = m.group(1).strip()
                        team = m.group(2).strip().upper()
                        if name and team:
                            return f"{name}_{team}"
                    # Fallback: just name
                    name_only = s.split("(")[0].strip()
                    return name_only or None

                for row in r:
                    lineup = []
                    for pos in positions:
                        if pos in row and row[pos]:
                            key = parse_key(row[pos])
                            if key:
                                lineup.append(key)
                    if len(lineup) == 8:  # Valid lineup has 8 players
                        lineups.append(sorted(lineup))
                return lineups


def _write_lineups_long(lineups: List[List[str]], path: str, prefix: str = "var"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lineup_id", "player_id"])
        for i, lu in enumerate(lineups, start=1):
            lid = f"{prefix}_{i}"
            for pid in lu:
                w.writerow([lid, pid])


# ---------- Helpers ----------


def _sum(pool: Dict[str, Player], lu: Iterable[str], attr: str) -> float:
    return sum(getattr(pool[p], attr) for p in lu)


def _salary(pool: Dict[str, Player], lu: Iterable[str]) -> int:
    return sum(pool[p].salary for p in lu)


def _hamming(a: List[str], b: List[str]) -> int:
    """Count different players between two 8-man sets as the number of players in `a` not in `b`.
    For equal-sized lineups this equals swaps needed; a single swap returns 1.
    """
    sa, sb = set(a), set(b)
    return len(sa - sb)


def _is_valid_slots(pool: Dict[str, Player], lineup: List[str]) -> bool:
    """True iff players in `lineup` can be assigned to DK slots (PG,SG,SF,PF,C,G,F,UTIL).
    Works for partial lineups by attempting a backtracking assignment over eligible slots.
    """
    if not lineup:
        return True
    # Reject duplicate players outright
    if len(lineup) != len(set(lineup)):
        return False

    # Precompute eligible slots per player (union across all positions)
    def eligible_slots(pid: str) -> List[str]:
        slots: List[str] = []
        for pos in pool[pid].positions:
            slots.extend(POS_TO_SLOTS.get(pos, ["UTIL"]))
        # stable de-duplication preserving first-seen order
        seen: set[str] = set()
        uniq: List[str] = []
        for s in slots:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq

    # Prioritize tighter slots to reduce branching
    slot_priority = {
        "C": 0,
        "PF": 1,
        "SF": 1,
        "PG": 2,
        "SG": 2,
        "G": 3,
        "F": 3,
        "UTIL": 4,
    }

    order = list(lineup)
    try:
        order.sort(key=lambda p: (len(eligible_slots(p)), slot_priority.get(pool[p].pos, 5)))
    except KeyError:
        # pid not found in pool ⇒ invalid
        _dprint("_is_valid_slots: unknown pid in pool during sort", {"lineup": lineup})
        return False

    used: set[str] = set()

    def dfs(i: int) -> bool:
        if i == len(order):
            return True
        pid = order[i]
        for s in sorted(eligible_slots(pid), key=lambda x: slot_priority.get(x, 5)):
            if s in used:
                continue
            used.add(s)
            if dfs(i + 1):
                return True
            used.remove(s)
        return False

    ok = dfs(0)
    if not ok:
        if _debug_enabled():
            detail = {pid: eligible_slots(pid) for pid in lineup if pid in pool}
            _dprint("_is_valid_slots failed", {"order": order, "elig": detail})
    return ok


def _assign_slots(pool: Dict[str, Player], lineup: List[str]) -> List[Tuple[str, str]] | None:
    """Return an assignment [(slot, player_id), ...] if lineup can be DK-slot assigned; else None.
    Deterministic backtracking using same ordering heuristic as _is_valid_slots.
    """
    if not lineup:
        return []
    # Reject duplicate players outright
    if len(lineup) != len(set(lineup)):
        return None

    def eligible_slots(pid: str) -> List[str]:
        slots: List[str] = []
        for pos in pool[pid].positions:
            slots.extend(POS_TO_SLOTS.get(pos, ["UTIL"]))
        seen: set[str] = set()
        uniq: List[str] = []
        for s in slots:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq

    slot_priority = {
        "C": 0,
        "PF": 1,
        "SF": 1,
        "PG": 2,
        "SG": 2,
        "G": 3,
        "F": 3,
        "UTIL": 4,
    }

    order = list(lineup)
    try:
        order.sort(key=lambda p: (len(eligible_slots(p)), slot_priority.get(pool[p].pos, 5)))
    except KeyError:
        _dprint("_assign_slots: unknown pid in pool during sort", {"lineup": lineup})
        return None

    used: set[str] = set()
    assign: List[Tuple[str, str]] = []  # (slot, pid)

    def dfs(i: int) -> bool:
        if i == len(order):
            return True
        pid = order[i]
        for s in sorted(eligible_slots(pid), key=lambda x: slot_priority.get(x, 5)):
            if s in used:
                continue
            used.add(s)
            assign.append((s, pid))
            if dfs(i + 1):
                return True
            assign.pop()
            used.remove(s)
        return False

    ok = dfs(0)
    if not ok:
        if _debug_enabled():
            detail = {pid: eligible_slots(pid) for pid in lineup if pid in pool}
            _dprint("_assign_slots failed", {"order": order, "elig": detail})
        return None
    # We need to return in DK slot order, not search order
    by_slot = {s: pid for s, pid in assign}
    out = []
    for s in SLOTS:
        if s in by_slot:
            out.append((s, by_slot[s]))
    return out


def _pick_bucket(cfg: Config) -> Tuple[int, int]:
    return _rng.choices(cfg.salary_buckets, weights=cfg.salary_mix, k=1)[0]


def _pick_bucket_for_base(cfg: Config, base_salary: int) -> Tuple[int, int]:
    """Pick a salary bucket relative to the base lineup's salary.
    Always respect the DK lower bound and slightly widen the window for
    very high-salary bases to avoid infeasible searches.
    """
    window = int(getattr(cfg, "relative_salary_window", 700) or 700)
    hi = DK_SAL_HI
    # Default lower bound tied to base salary, but never below DK floor
    lo = max(DK_SAL_LO, base_salary - window)
    # If the base is within $200 of the cap, widen the search a bit
    if base_salary >= DK_SAL_HI - 200:
        lo = max(DK_SAL_LO, base_salary - max(window, 900))
    return (lo, hi)


# ----------- Validator utility -----------
def _validate_lineup(
    pool: Dict[str, Player],
    lineup: List[str],
    lo: int | None = None,
    hi: int | None = None,
) -> tuple[bool, str]:
    """Hard validator: slot-assignable to exactly the 8 DK slots and salary within [lo,hi] if provided.
    Returns (ok, reason_if_not_ok).
    """
    # Reject duplicate players
    if len(lineup) != len(set(lineup)):
        return (False, "duplicate player(s) in lineup")
    # IDs exist
    for pid in lineup:
        if pid not in pool:
            return (False, f"unknown player_id {pid}")
    # Slot feasibility must assign exactly 8 unique DK slots
    assign = _assign_slots(pool, lineup)
    if assign is None:
        return (False, "slot assignment failed")
    if len(assign) != 8:
        return (False, f"assigned {len(assign)} slots (expected 8)")
    used_slots = {s for s, _ in assign}
    if used_slots != set(SLOTS):
        return (False, f"assigned slots mismatch: {sorted(used_slots)}")
    # Salary bounds
    if lo is not None or hi is not None:
        sal = _salary(pool, lineup)
        if lo is not None and sal < lo:
            return (False, f"salary {sal} < lo {lo}")
        if hi is not None and sal > hi:
            return (False, f"salary {sal} > hi {hi}")
    return (True, "")


def _greedy_variant(
    base: List[str],
    pool: Dict[str, Player],
    cfg: Config,
    bucket: Tuple[int, int],
    use_ceil: bool = False,
) -> List[str] | None:
    lo, hi = bucket
    metric = "ceil" if use_ceil else "proj"

    # Replace min_uniques, sometimes +1 for more flexibility
    k = cfg.min_uniques + (1 if _rng.random() < 0.35 else 0)
    k = min(k, 4, len(base))  # soft cap

    # pick “victims”: highest own, then lower proj
    victims = sorted(base, key=lambda p: (pool[p].own, -pool[p].proj), reverse=True)[:k]
    keepers = [p for p in base if p not in victims]
    _dprint(
        "_greedy_variant start",
        {
            "base": base,
            "k": k,
            "victims": victims,
            "keepers": keepers,
            "bucket": (lo, hi),
            "use_ceil": use_ceil,
        },
    )

    # candidate lists for each victim (prefer same-pos; fallback to any)
    candidate_lists: List[List[Player]] = []
    for v in victims:
        vpos = set(pool[v].positions)
        cands = [
            pl
            for pl in pool.values()
            if pl.id != v and pl.id not in keepers and (vpos & set(pl.positions))
        ]
        if not cands:
            cands = [pl for pl in pool.values() if pl.id != v and pl.id not in keepers]

        # rank: projection/ceil, then prefer higher salary (no ownership penalty here)
        cands.sort(key=lambda x: (getattr(x, metric), x.salary), reverse=True)
        candidate_lists.append(cands)

    lineup = keepers[:]
    used = set(lineup)

    # place replacements for victims (ONLY enforce <= upper bound here)
    for cands in candidate_lists:
        placed = False
        for pl in cands:
            if pl.id in used:
                continue
            test = lineup + [pl.id]
            if not _is_valid_slots(pool, test):
                continue
            if _salary(pool, test) <= hi:
                lineup = test
                used.add(pl.id)
                placed = True
                _dprint(
                    "placed victim replacement",
                    {"pid": pl.id, "salary": _salary(pool, lineup)},
                )
                break
        if not placed:
            _dprint("failed to place replacement for a victim")
            return None

    # fill to 8 (still only enforce <= hi)
    while len(lineup) < 8:
        placed = False
        for pl in sorted(
            pool.values(),
            key=lambda x: (getattr(x, metric), x.salary),
            reverse=True,
        ):
            if pl.id in used:
                continue
            test = lineup + [pl.id]
            if _is_valid_slots(pool, test) and _salary(pool, test) <= hi:
                lineup = test
                used.add(pl.id)
                placed = True
                _dprint("filled slot", {"pid": pl.id, "salary": _salary(pool, lineup)})
                break
        if not placed:
            _dprint("failed to fill to 8")
            return None

    # FINAL salary check: must be in [lo, hi]. If below lo, try upgrades.
    sal = _salary(pool, lineup)
    if sal < lo:
        # simple upgrade pass: try to swap one player at a time to raise salary
        for up_iter in range(100):  # larger budget when chasing floor
            made_swap = False
            for idx, pid in enumerate(list(lineup)):
                pl_old = pool[pid]
                # try pricier candidates that still fit slots and don't crush metric
                for pl_new in sorted(pool.values(), key=lambda x: x.salary, reverse=True):
                    if pl_new.id in used or pl_new.id == pid:
                        continue
                    if pl_new.salary <= pl_old.salary:
                        continue
                    # mild guard on quality, allow more drop after 60 iters:
                    allowed_drop = 0.5 if up_iter < 60 else 1.25
                    if (getattr(pl_new, metric) + allowed_drop) < getattr(pl_old, metric):
                        continue
                    test = lineup[:idx] + [pl_new.id] + lineup[idx + 1 :]
                    if not _is_valid_slots(pool, test):
                        continue
                    new_sal = _salary(pool, test)
                    if new_sal <= hi and new_sal > sal:
                        used.remove(pid)
                        used.add(pl_new.id)
                        lineup = sorted(test)
                        sal = new_sal
                        made_swap = True
                        _dprint("upgrade swap", {"out": pid, "in": pl_new.id, "salary": sal})
                        break
                if made_swap:
                    break
            if not made_swap:
                break

    if not (lo <= sal <= hi):
        _dprint(
            "final salary out of range",
            {
                "salary": sal,
                "lo": lo,
                "hi": hi,
                "hint": "consider widening relative_salary_window or check high-salary base",
            },
        )
        return None

    # ownership cap
    if _sum(pool, lineup, "own") > cfg.max_total_own:
        _dprint(
            "ownership cap exceeded",
            {"own_sum": _sum(pool, lineup, "own"), "cap": cfg.max_total_own},
        )
        return None

    ok, _why = _validate_lineup(pool, lineup, lo, hi)
    if not ok:
        _dprint("validator failed at end of _greedy_variant", {"why": _why})
        return None
    _dprint(
        "_greedy_variant ok",
        {
            "salary": sal,
            "own": _sum(pool, lineup, "own"),
            "assign": _assign_slots(pool, lineup),
        },
    )
    return sorted(lineup)


# ---------- Core ----------


def build_variants(
    optimizer_lineups_path: str | None = None,
    player_pool_path: str | None = None,
    out_path: str | None = None,
    cfg_dict: dict | None = None,
) -> dict:
    # Use defaults if not provided
    if optimizer_lineups_path is None:
        optimizer_lineups_path = str(paths.OPTIMIZER_PATH)
    if player_pool_path is None:
        player_pool_path = str(paths.PLAYER_POOL)
    if out_path is None:
        out_path = str(paths.VARIANT_CATALOG)

    # Backward compatibility: ignore deprecated keys such as 'max_exposure'
    _raw_cfg = dict(cfg_dict or {})
    _raw_cfg.pop("max_exposure", None)
    cfg = Config(**_raw_cfg)
    _rng.seed(cfg.random_seed)

    pool = _read_player_pool(str(player_pool_path))
    bases = _read_lineups_long(str(optimizer_lineups_path))

    warnings: List[str] = []
    # Robustly resolve/match base lineup player_ids to pool keys
    import re as _re

    id_re = _re.compile(r"^(.+)_([A-Z]{2,4})_(\d+)(?:_\d+)?$")

    def _resolve_pid_from_pool(pid: str) -> str | None:
        if pid in pool:
            return pid
        m = id_re.match(pid)
        if m:
            name, team, sal = m.group(1), m.group(2), int(m.group(3))
            k_nts = f"{name}_{team}_{sal}"
            if k_nts in pool:
                return k_nts
            k_nt = f"{name}_{team}"
            if k_nt in pool:
                return k_nt
        # As a last resort try raw name
        if pid in pool:
            return pid
        return None

    filtered_bases: List[List[str]] = []
    dropped = 0
    missing_sample: set[str] = set()
    for b in bases:
        mapped: List[str] = []
        ok = True
        for pid in b:
            mp = _resolve_pid_from_pool(str(pid))
            if mp is None or mp not in pool:
                ok = False
                missing_sample.add(str(pid))
                break
            mapped.append(mp)
        if ok and len(mapped) == 8 and len(set(mapped)) == 8:
            filtered_bases.append(sorted(mapped))
        else:
            dropped += 1
    if dropped:
        sample_ids = ", ".join(sorted(list(missing_sample))[:5])
        warnings.append(f"Dropped {dropped} base lineup(s) due to missing IDs: e.g., {sample_ids}")
    bases = filtered_bases

    bank: List[List[str]] = []
    base_proj = {tuple(b): _sum(pool, b, "proj") for b in bases}

    for b in bases:
        bproj = base_proj[tuple(b)]
        bsal = _salary(pool, b)
        accepted_for_base = 0
        for i in range(cfg.variants_per_base):
            # Use relative bucket based on base salary instead of fixed buckets
            bucket = _pick_bucket_for_base(cfg, bsal)
            k = int(getattr(cfg, "ceil_toggle_k", 3) or 0)
            use_ceil = k > 0 and ((i + 1) % k == 0)
            v = _greedy_variant(b, pool, cfg, bucket, use_ceil=use_ceil)
            if not v:
                continue
            if _sum(pool, v, "proj") < bproj - cfg.projection_delta:
                continue
            if _hamming(v, b) < cfg.min_uniques:
                continue
            if any(_hamming(v, x) < cfg.global_min_distance for x in bank):
                continue
            lo, hi = bucket
            ok_v, _w = _validate_lineup(pool, v, lo, hi)
            if ok_v:
                bank.append(v)
            accepted_for_base += 1

        # Prepare a baseline victims/keepers split for failsafe construction
        # Use the same heuristic as _greedy_variant: highest own, then lower proj
        k_fail = min(max(1, cfg.min_uniques), len(b))
        victims_fs = sorted(b, key=lambda p: (pool[p].own, -pool[p].proj), reverse=True)[:k_fail]
        keepers = [p for p in b if p not in victims_fs]

        # Diversity failsafe: if a base produced nothing, try a couple of random victim selections
        if accepted_for_base == 0:
            for _ in range(2):
                metric = "proj"
                # De-duplicate candidates by player_id and skip keepers
                uniq_by_id = {}
                for pl in pool.values():
                    if pl.id in keepers or pl.id in uniq_by_id:
                        continue
                    uniq_by_id[pl.id] = pl
                cands = sorted(
                    uniq_by_id.values(),
                    key=lambda x: (getattr(x, metric), x.salary),
                    reverse=True,
                )
                trial = keepers[:]
                seen_ids = set(trial)
                for pl in cands:
                    if len(trial) >= 8:
                        break
                    if pl.id in seen_ids:
                        continue
                    t2 = trial + [pl.id]
                    if _is_valid_slots(pool, t2):
                        trial = t2
                        seen_ids.add(pl.id)
                if len(trial) == 8:
                    lo, hi = _pick_bucket_for_base(cfg, bsal)
                    if (
                        _sum(pool, trial, "proj") >= bproj - cfg.projection_delta
                        and _sum(pool, trial, "own") <= cfg.max_total_own
                        and _hamming(trial, b) >= cfg.min_uniques
                        and all(_hamming(trial, x) >= cfg.global_min_distance for x in bank)
                    ):
                        ok_t, _w2 = _validate_lineup(pool, trial, lo, hi)
                        if ok_t:
                            bank.append(sorted(trial))
                            break

    # Build variants-only long DataFrame with slot assignment
    rows: List[dict] = []
    for i, lu in enumerate(bank, start=1):
        lid = f"var_{i}"
        ok, why = _validate_lineup(pool, lu, DK_SAL_LO, DK_SAL_HI)
        if not ok:
            # Skip emission of invalid lineups entirely; they failed earlier but double guard here.
            continue
        assignment = _assign_slots(pool, lu)
        for slot, pid in assignment:  # type: ignore[arg-type]
            rows.append({"lineup_id": lid, "slot": slot, "player_id": pid})

    # Persist if an explicit out_path was provided (backward compat), else return only
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if Path(out_path).suffix.lower() == ".parquet":
            pd.DataFrame(rows, columns=["lineup_id", "slot", "player_id"]).to_parquet(
                out_path, index=False
            )
        else:
            with open(out_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["lineup_id", "slot", "player_id"])
                for r in rows:
                    w.writerow([r["lineup_id"], r["slot"], r["player_id"]])

    return {
        "ok": True,
        "n_bases": len(bases),
        "n_variants": len(bank),
        "out_path": str(out_path) if out_path else "",
        "variants_df": (
            pd.DataFrame(rows, columns=["lineup_id", "slot", "player_id"])
            if rows
            else pd.DataFrame(columns=["lineup_id", "slot", "player_id"])
        ),
        "warnings": warnings,
    }


def build_and_write(
    optimizer_lineups_path: str,
    player_pool_path: str,
    out_path: str,
    cfg_json: str | dict,
):
    cfg = json.loads(cfg_json) if isinstance(cfg_json, str) else cfg_json
    return build_variants(optimizer_lineups_path, player_pool_path, out_path, cfg)


def build_variants_df_from_dfs(
    pool_df: pd.DataFrame, bases_long_df: pd.DataFrame, cfg_dict: dict | None = None
) -> pd.DataFrame:
    """Generate variants-only long DataFrame from in-memory DataFrames.
    - pool_df should have canonical columns: player_id, name, team, pos, salary, proj, ceil, own
    - bases_long_df must have: lineup_id, player_id (slot optional)

    This function is resilient to missing or non‑matching `player_id`s in `pool_df` by
    synthesizing stable keys from (name, team, salary) and mapping base lineup IDs like
    "Name_Team_5500_12345" to the pool using the "Name_Team_5500" prefix.
    """
    _raw_cfg = dict(cfg_dict or {})
    _raw_cfg.pop("max_exposure", None)
    cfg = Config(**_raw_cfg)
    _rng.seed(cfg.random_seed)

    # Build pool dict with robust ID mapping
    pool: Dict[str, Player] = {}
    pdf = pool_df.copy()
    # Normalize fields/types
    pdf["name"] = pdf["name"].astype(str)
    pdf["team"] = pdf["team"].astype(str)
    pdf["pos"] = (
        pdf["pos"]
        .astype(str)
        .str.replace("|", "/", regex=False)
        .str.replace(",", "/", regex=False)
        .str.replace(" ", "", regex=False)
    )
    pdf["salary"] = pd.to_numeric(pdf["salary"], errors="coerce").fillna(0).astype("int64")
    pdf["proj"] = pd.to_numeric(pdf["proj"], errors="coerce").fillna(0.0).astype("float64")
    pdf["ceil"] = pd.to_numeric(pdf["ceil"], errors="coerce").fillna(pdf["proj"]).astype("float64")
    pdf["own"] = pd.to_numeric(pdf["own"], errors="coerce").fillna(0.0).astype("float64")

    # Synthesize alternate keys for resilient joins
    def _mk_nt(name: Any, team: Any) -> str:
        return f"{str(name)}_{str(team)}".strip()

    def _mk_nts(name: Any, team: Any, salary: Any) -> str:
        return f"{str(name)}_{str(team)}_{int(_as_int(salary))}".strip()

    # Dictionaries to allow lookup by various keys
    by_id: Dict[str, Player] = {}
    by_nts: Dict[str, Player] = {}
    by_nt: Dict[str, Player] = {}

    for r in pdf[["player_id", "name", "team", "pos", "salary", "proj", "ceil", "own"]].itertuples(
        index=False, name="Row"
    ):
        pid_raw = str(r.player_id) if r.player_id is not None else ""
        pid = pid_raw.strip()
        poss = [p for p in str(r.pos).split("/") if p]
        if not poss:
            poss = ["UTIL"]
        pl = Player(
            id=pid if pid else _mk_nts(str(r.name), str(r.team), int(r.salary)),
            pos=poss[0],
            positions=poss,
            team=str(r.team),
            salary=_as_int(r.salary),
            proj=_as_float(r.proj),
            ceil=_as_float(r.ceil) if pd.notna(r.ceil) else _as_float(r.proj),
            own=_as_float(r.own) if pd.notna(r.own) else 0.0,
        )
        # Primary id (if present)
        if pid:
            by_id.setdefault(pid, pl)
            pool[pid] = pl
        # Alternate keys
        k_nts = _mk_nts(r.name, r.team, r.salary)
        k_nt = _mk_nt(r.name, r.team)
        if k_nts not in pool:
            by_nts.setdefault(k_nts, pl)
            pool.setdefault(k_nts, pl)  # allow direct lookup by prefix key
        if k_nt not in pool:
            by_nt.setdefault(k_nt, pl)
            pool.setdefault(k_nt, pl)

    # Resolve base lineup IDs to pool keys. Accept exact match, else
    # try "Name_Team_Salary_XXXX" → "Name_Team_Salary" prefix; else name+team.
    import re

    id_re = re.compile(r"^(.+)_([A-Z]{2,4})_(\d+)(?:_\d+)?$")

    def _resolve_pid(bpid: str) -> str | None:
        bpid = str(bpid).strip()
        if bpid in by_id:
            return bpid
        # Prefix form Name_Team_Salary[_id]
        m = id_re.match(bpid)
        if m:
            name, team, sal = m.group(1), m.group(2), int(m.group(3))
            k_nts = _mk_nts(name, team, sal)
            if k_nts in by_nts:
                return k_nts
            k_nt = _mk_nt(name, team)
            if k_nt in by_nt:
                # If multiple candidates under k_nt, prefer closest salary
                # Collect candidates by scanning pdf once
                cand = pdf[(pdf["name"] == name) & (pdf["team"] == team)]
                if not cand.empty:
                    cand = cand.iloc[(cand["salary"] - sal).abs().argsort()]
                    name_team_best = _mk_nts(name, team, int(cand.iloc[0]["salary"]))
                    if name_team_best in by_nts:
                        return name_team_best
                return k_nt
        # As a last resort, try raw name match ignoring team/salary (rare)
        hits = pdf[pdf["name"] == bpid]
        if len(hits) == 1:
            row = hits.iloc[0]
            return _mk_nts(str(row["name"]), str(row["team"]), int(row["salary"]))
        return None

    # Build bases from resolved IDs, dropping any lineup with unresolved players
    bases: List[List[str]] = []
    for lid, grp in bases_long_df.groupby("lineup_id"):
        raw_pids = [str(p) for p in grp["player_id"].astype(str).tolist()]
        mapped: List[str] = []
        ok = True
        for pid in raw_pids:
            mp = _resolve_pid(pid)
            if mp is None or mp not in pool:
                ok = False
                break
            mapped.append(mp)
        if ok and len(mapped) == 8 and len(set(mapped)) == 8:
            bases.append(sorted(mapped))

    bank: List[List[str]] = []
    base_proj = {tuple(b): _sum(pool, b, "proj") for b in bases}
    for b in bases:
        bproj = base_proj[tuple(b)]
        bsal = _salary(pool, b)
        accepted_for_base = 0
        for i in range(cfg.variants_per_base):
            bucket = _pick_bucket_for_base(cfg, bsal)
            k = int(getattr(cfg, "ceil_toggle_k", 3) or 0)
            use_ceil = k > 0 and ((i + 1) % k == 0)
            v = _greedy_variant(b, pool, cfg, bucket, use_ceil=use_ceil)
            if not v:
                continue
            if _sum(pool, v, "proj") < bproj - cfg.projection_delta:
                continue
            if _hamming(v, b) < cfg.min_uniques:
                continue
            if any(_hamming(v, x) < cfg.global_min_distance for x in bank):
                continue
            lo, hi = bucket
            ok_v, _w = _validate_lineup(pool, v, lo, hi)
            if ok_v:
                bank.append(v)
            accepted_for_base += 1

        # Prepare victims/keepers for failsafe
        k_fail = min(max(1, cfg.min_uniques), len(b))
        victims_fs = sorted(b, key=lambda p: (pool[p].own, -pool[p].proj), reverse=True)[:k_fail]
        keepers = [p for p in b if p not in victims_fs]

        if accepted_for_base == 0:
            for _ in range(2):
                metric = "proj"
                # De-duplicate candidates by player_id and skip keepers
                uniq_by_id = {}
                for pl in pool.values():
                    if pl.id in keepers or pl.id in uniq_by_id:
                        continue
                    uniq_by_id[pl.id] = pl
                cands = sorted(
                    uniq_by_id.values(),
                    key=lambda x: (getattr(x, metric), x.salary),
                    reverse=True,
                )
                trial = keepers[:]
                seen_ids = set(trial)
                for pl in cands:
                    if len(trial) >= 8:
                        break
                    if pl.id in seen_ids:
                        continue
                    t2 = trial + [pl.id]
                    if _is_valid_slots(pool, t2):
                        trial = t2
                        seen_ids.add(pl.id)
                if len(trial) == 8:
                    lo, hi = _pick_bucket_for_base(cfg, bsal)
                    if (
                        _sum(pool, trial, "proj") >= bproj - cfg.projection_delta
                        and _sum(pool, trial, "own") <= cfg.max_total_own
                        and _hamming(trial, b) >= cfg.min_uniques
                        and all(_hamming(trial, x) >= cfg.global_min_distance for x in bank)
                    ):
                        ok_t, _w2 = _validate_lineup(pool, trial, lo, hi)
                        if ok_t:
                            bank.append(sorted(trial))
                            break

    rows: List[dict] = []
    for i, lu in enumerate(bank, start=1):
        lid = f"var_{i}"
        ok, why = _validate_lineup(pool, lu, DK_SAL_LO, DK_SAL_HI)
        if not ok:
            continue
        assignment = _assign_slots(pool, lu)
        for slot, pid in assignment:  # type: ignore[arg-type]
            rows.append({"lineup_id": lid, "slot": slot, "player_id": pid})

    return (
        pd.DataFrame(rows, columns=["lineup_id", "slot", "player_id"])
        if rows
        else pd.DataFrame(columns=["lineup_id", "slot", "player_id"])
    )
