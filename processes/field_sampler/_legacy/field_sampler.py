# Field Sampler – build entrants and live lineups with replacement
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import yaml
from src.config import paths

import warnings

warnings.warn(
    "processes.field_sampler._legacy.field_sampler is deprecated; use field_sampler.engine",
    DeprecationWarning,
    stacklevel=2,
)

ALLOWED_SLOTS = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}


# PID normalizer helper
def _normalize_pid(v: Any) -> str:
    """Return a stable string player_id. Handles ints, floats ending with .0, and strings."""
    try:
        import numpy as _np
    except Exception:
        _np = None
    # numpy integers
    if _np is not None and isinstance(v, _np.integer):
        return str(int(v))
    # native ints
    if isinstance(v, int):
        return str(v)
    # floats that are actually integers
    if isinstance(v, float):
        if math.isfinite(v):
            iv = int(round(v))
            if abs(v - iv) < 1e-9:
                return str(iv)
        return str(v)
    # strings: strip trailing .0 if present
    if isinstance(v, str):
        s = v.strip()
        if s.endswith(".0") and s.replace(".", "", 1).isdigit():
            try:
                return str(int(float(s)))
            except Exception:
                return s
        return s
    # fallback
    return str(v)


@dataclass
class Weights:
    weight_proj: float = 0.030
    weight_salary: float = 0.00008
    weight_own: float = 0.45
    weight_chalk_cnt: float = 0.12
    bias: float = -6.0


@dataclass
class BucketTarget:
    run_id: str | None = None
    salary_bin: str | None = None  # "low", "mid", "high"
    ownership_tertile: str | None = None  # "low_own", "mid_own", "high_own"
    target_share: float = 0.0  # Target percentage of field


@dataclass
class BucketTelemetry:
    realized_shares: dict[str, float]
    bucket_deviation: float  # Max deviation from targets
    gini_coefficient: float
    top_dupes: list[tuple[str, int]]  # (lineup_hash, count) pairs
    player_exposures: dict[str, float]  # player_id -> exposure %


SPORT_DEFAULT_CAP = {
    "NBA_CLASSIC": 0.008,
    "NFL_CLASSIC": 0.012,
    "NFL_SHOWDOWN": 0.025,
    "MMA": 0.015,
    "NASCAR": 0.015,
    "PGA": 0.005,
}


SPORT_SALARY_CAPS = {
    "NBA_CLASSIC": 50000,
    "NFL_CLASSIC": 50000,
    "NFL_SHOWDOWN": 50000,
    "MMA": 50000,
    "NASCAR": 50000,
    "PGA": 50000,
}


# Resolver helpers for catalog/pool directory or file path
def _resolve_catalog_path(path: str) -> str:
    """Accept a file path or a run directory. Prefer parquet if present."""
    if os.path.isdir(path):
        # preferred filenames in order
        candidates = [
            os.path.join(path, "variant_catalog.parquet"),
            os.path.join(path, "lineups_grid.parquet"),
            os.path.join(path, "lineups_grid.csv"),
        ]
        for c in candidates:
            if os.path.exists(c):
                print(f"[FIELD] Using catalog file: {c}")
                return c
        raise FileNotFoundError(
            f"No catalog file found under {path}. Expected one of: {', '.join(os.path.basename(c) for c in candidates)}"
        )
    return path


def _resolve_pool_path(path: str) -> str:
    """Accept a file path or a run directory. Prefer parquet if present."""
    if os.path.isdir(path):
        candidates = [
            os.path.join(path, "player_pool.parquet"),
            os.path.join(path, "player_pool.csv"),
        ]
        for c in candidates:
            if os.path.exists(c):
                print(f"[FIELD] Using player pool file: {c}")
                return c
        raise FileNotFoundError(
            f"No player pool file found under {path}. Expected one of: {', '.join(os.path.basename(c) for c in candidates)}"
        )
    return path


def _read_pool(path: str) -> dict[str, dict]:
    import pandas as pd

    pool: dict[str, dict] = {}
    scaled = 0

    # Handle both parquet and CSV files
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    # Detect ID column
    id_col = None
    for cand in (
        "player_id",
        "contest_player_id",
        "dk_id",
        "id",
        "PLAYERID",
        "PlayerID",
    ):
        if cand in df.columns:
            id_col = cand
            break
    if id_col is None:
        raise ValueError(
            f"Player pool missing an ID column; looked for one of: player_id, contest_player_id, dk_id, id. Columns present: {list(df.columns)}"
        )
    print(f"[FIELD] Pool ID column: {id_col} (rows={len(df)})")

    # Detect positions column (optional)
    pos_col = None
    for cand in ("positions", "position", "pos", "POSITIONS", "Position"):
        if cand in df.columns:
            pos_col = cand
            break

    # Detect ownership column name
    own_col = None
    for cand in ("own_proj", "own", "ownership", "OWN", "Ownership"):
        if cand in df.columns:
            own_col = cand
            break

    for _, row in df.iterrows():
        # Ownership with auto-scale if in 0-1 range
        own_raw = (
            float(row.get(own_col, 0.0))
            if own_col is not None and not pd.isna(row.get(own_col))
            else 0.0
        )
        if math.isnan(own_raw) or own_raw < 0:
            own = 0.0
        elif 0.0 <= own_raw <= 1.5:
            own = own_raw * 100.0
            scaled += 1
        else:
            own = min(100.0, own_raw)

        pid = _normalize_pid(row[id_col])
        pool[pid] = {
            "proj": float(row["proj"]),
            "own": float(own),
            "salary": int(float(row["salary"])),
        }
        if pos_col is not None and not pd.isna(row.get(pos_col, None)):
            pool[pid]["positions"] = str(row[pos_col])

    if scaled:
        print(f"[INFO] Scaled ownership from fraction→percent for {scaled} players.")
    return pool


def _read_long(path: str) -> list[list[tuple[str, str]]]:
    """
    Return list of lineups; each lineup is a list of (slot, player_id) tuples.

    Supported schemas:
    - Long w/ slots: columns include lineup_id, player_id, slot
    - Long no slots: columns include lineup_id, player_id (assign default NBA slots)
    - Wide: columns include many of [PG, SG, SF, PF, C, G, F, UTIL]
    """
    import pandas as pd

    roster_order = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    wide_headers = set(roster_order)

    # Handle both parquet and CSV files
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    flds = set(df.columns)
    by = defaultdict(list)

    if {"lineup_id", "player_id", "slot"}.issubset(flds):
        # Slot-aware catalog (preferred)
        for _, row in df.iterrows():
            by[row["lineup_id"]].append((row["slot"], _normalize_pid(row["player_id"])))

        def sort_key(sp):  # stable slot order
            return roster_order.index(sp[0]) if sp[0] in roster_order else 999

        result = [sorted(sp, key=sort_key) for _, sp in sorted(by.items())]
        print(f"[FIELD] Catalog schema: LONG+SLOTS (rows={len(by)})")
        return result

    elif {"lineup_id", "player_id"}.issubset(flds):
        # Legacy catalog: no slot column. Assign default slots in order.
        for _, row in df.iterrows():
            by[row["lineup_id"]].append(_normalize_pid(row["player_id"]))
        out: list[list[tuple[str, str]]] = []
        truncated_lineups = 0
        for _, pids in sorted(by.items()):
            if len(pids) > 8:
                truncated_lineups += 1
            assigned: list[tuple[str, str]] = []
            n = min(len(pids), len(roster_order))
            for i in range(n):
                assigned.append((roster_order[i], pids[i]))
            out.append(assigned)
        if truncated_lineups > 0:
            print(
                f"[WARN] Truncated {truncated_lineups} legacy lineups with >8 players to exactly 8 slots."
            )
        print(f"[FIELD] Catalog schema: LONG (rows={len(out)})")
        return out

    elif len(wide_headers & flds) >= 5:
        # Wide catalog: one row per lineup with slot columns
        headers = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        out: list[list[tuple[str, str]]] = []
        for _, row in df.iterrows():
            assigned: list[tuple[str, str]] = []
            for slot in headers:
                pid = row.get(slot, None)
                if pid is None:
                    continue
                if isinstance(pid, float) and np.isnan(pid):
                    continue
                if pid == "":
                    continue
                assigned.append((slot, _normalize_pid(pid)))
            if assigned:
                out.append(assigned)
        print(f"[FIELD] Catalog schema: WIDE (rows={len(out)})")
        return out

    else:
        raise ValueError(
            f"{path} must include a supported schema: long with (lineup_id,player_id[,slot]) or wide slot columns (PG..UTIL). Columns present: {sorted(flds)}"
        )


def _write_long(lineups: list[list[tuple[str, str]]], path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lineup_id", "slot", "player_id"])
        for i, lu in enumerate(lineups, start=1):
            lid = f"L{i}"
            for slot, pid in lu:
                w.writerow([lid, slot, pid])


def _write_tournament_wide(lineups: list[list[tuple[str, str]]], path: str):
    headers = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for lu in lineups:
            row = {slot: pid for slot, pid in lu}
            w.writerow([row.get(h, "") for h in headers])


def _write_simulator_tournament_wide(lineups: list[list[tuple[str, str]]], path: str):
    """Write tournament lineups for simulator: headerless, IDs only."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    headers = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for lu in lineups:
            row = {slot: pid for slot, pid in lu}
            w.writerow([row.get(h, "") for h in headers])


def _validate_catalog(
    catalog: list[list[tuple[str, str]]], pool: dict[str, dict], name: str
) -> None:
    """Validate that all player IDs in catalog exist in the player pool."""
    bad = []
    for i, lu in enumerate(catalog):
        for _, pid in lu:
            if pid not in pool:
                bad.append((i, pid))
                break
    if bad:
        preview = ", ".join(f"(lineup_idx={i}, pid={pid})" for i, pid in bad[:5])
        raise ValueError(
            f"{name} contains lineups with unknown player IDs: {preview} ... (total {len(bad)})"
        )


def _validate_salary_cap(
    catalog: list[list[tuple[str, str]]], pool: dict[str, dict], sport: str, name: str
) -> None:
    """Validate that all lineups respect salary cap for the given sport."""
    salary_cap = SPORT_SALARY_CAPS.get(sport.upper())
    if salary_cap is None:
        return  # No validation for unknown sports

    violations = []
    for i, lu in enumerate(catalog):
        total_salary = sum(pool[p]["salary"] for _, p in lu if p in pool)
        if total_salary > salary_cap:
            violations.append((i, total_salary))

    if violations:
        preview = ", ".join(
            f"(lineup_idx={i}, salary={sal})" for i, sal in violations[:5]
        )
        raise ValueError(
            f"{name} contains {len(violations)} lineups exceeding ${salary_cap:,} salary cap: {preview}"
        )


def _normalize_positions(v: Any) -> set:
    """Normalize positions from a string like 'PG/SG' or an iterable to a set of tokens."""
    if isinstance(v, str):
        return set(p.strip() for p in v.split("/") if p)
    if isinstance(v, (list, tuple, set)):
        return set(map(str, v))
    return set()


def _validate_slot_eligibility(
    catalog: list[list[tuple[str, str]]], pool: dict[str, dict], name: str
) -> None:
    """Validate slot eligibility if positions are present in pool."""
    # Check if any player has position data
    has_positions = any("positions" in player_data for player_data in pool.values())
    if not has_positions:
        return  # Skip validation if no position data

    POSITION_ELIGIBILITY = {
        "PG": {"PG"},
        "SG": {"SG"},
        "SF": {"SF"},
        "PF": {"PF"},
        "C": {"C"},
        "G": {"PG", "SG"},
        "F": {"SF", "PF"},
        "UTIL": {"PG", "SG", "SF", "PF", "C"},
    }

    violations = []
    for i, lu in enumerate(catalog):
        for slot, pid in lu:
            if pid not in pool:
                continue
            player_positions = _normalize_positions(pool[pid].get("positions", ""))
            allowed = POSITION_ELIGIBILITY.get(slot, set())
            if allowed and not (player_positions & allowed):
                violations.append((i, slot, pid, sorted(player_positions)))
                break
    if violations:
        preview = ", ".join(
            f"(lineup_idx={i}, slot={slot}, pid={pid}, pos={pos})"
            for i, slot, pid, pos in violations[:5]
        )
        raise ValueError(
            f"{name} contains {len(violations)} slot eligibility violations: {preview}"
        )


def _validate_lineup_shape(
    catalog: list[list[tuple[str, str]]], pool: dict[str, dict], name: str
) -> None:
    """Strict lineup shape validation: exactly 8 slots, valid slot names, no duplicate players, all PIDs present."""
    bad = []
    for i, lu in enumerate(catalog):
        slots = [s for s, _ in lu]
        pids = [p for _, p in lu]
        if len(lu) != 8:
            bad.append((i, "len!=8"))
            continue
        if any(s not in ALLOWED_SLOTS for s in slots):
            bad.append((i, "bad_slot"))
            continue
        if len(set(pids)) != 8:
            bad.append((i, "dup_pid"))
            continue
        if any(p not in pool for p in pids):
            bad.append((i, "pid_missing"))
            continue
    if bad:
        preview = ", ".join(map(str, bad[:5]))
        raise ValueError(
            f"{name} has invalid lineups, e.g. {preview} ... (total {len(bad)})"
        )


def _enforce_dup_cap_inplace(
    entrants: list[list[tuple[str, str]]],
    catalog: list[list[tuple[str, str]]],
    p: list[float],
    dup_mode: str,
    rng: np.random.Generator,
    protected_prefix_n: int,
    cap_abs: int | None,
) -> int | None:
    """Robust post-inject duplicate cap enforcement that protects the specified prefix entries."""
    if cap_abs is None:
        return cap_abs

    # Feasibility: if the cap is too tight to fill the field at all, relax minimally.
    unique_catalog = {tuple(lu) for lu in catalog}
    min_cap_needed = math.ceil(len(entrants) / max(1, len(unique_catalog)))
    if cap_abs < min_cap_needed:
        print(
            f"[WARN] cap_abs={cap_abs} infeasible for catalog_size={len(unique_catalog)} "
            f"and entrants={len(entrants)}; relaxing to {min_cap_needed}."
        )
        cap_abs = min_cap_needed

    # Map each lineup to the indices where it appears in entrants
    counts = Counter(tuple(lu) for lu in entrants)
    idxs_by_lineup = defaultdict(list)
    for i, lu in enumerate(entrants):
        idxs_by_lineup[tuple(lu)].append(i)

    # For sampling, represent catalog as tuples and track availability (< cap)
    cat_tuples = [tuple(lu) for lu in catalog]

    def sample_replacement(deny=None):
        """Sample a catalog lineup that won't exceed cap when added."""
        # Build an availability mask over catalog indices
        avail = np.fromiter(
            (counts[t] < cap_abs and t != deny for t in cat_tuples), dtype=bool
        )
        if not avail.any():
            return None  # nothing available without violating the cap

        if dup_mode == "multinomial":
            p_arr = np.asarray(p, dtype=float)
            p_arr = np.where(avail, p_arr, 0.0)
            s = p_arr.sum()
            if s <= 0:
                # fallback to uniform over available
                avail_idx = np.nonzero(avail)[0]
                j = int(rng.choice(avail_idx))
            else:
                j = int(rng.choice(len(catalog), p=p_arr / s))
        else:
            avail_idx = np.nonzero(avail)[0]
            j = int(rng.choice(avail_idx))
        return j

    # Trim overfull lineups; never replace protected prefix entries
    for lt in list(counts.keys()):
        while counts[lt] > cap_abs:
            # choose a replaceable index for this lineup that is NOT one of the protected entries
            replaceable = [i for i in idxs_by_lineup[lt] if i >= protected_prefix_n]
            if not replaceable:
                # Can't drop more without removing protected entries; stop trimming this lineup.
                break
            i2 = int(replaceable.pop())  # pop one index to replace
            idxs_by_lineup[lt].remove(i2)
            counts[lt] -= 1  # decrement now to make lt newly eligible if close to cap

            j = sample_replacement(deny=lt)
            if j is None:
                # No legal replacement without violating cap; revert and bail
                counts[lt] += 1
                idxs_by_lineup[lt].append(i2)
                print(
                    "[WARN] No available replacement under cap; leaving residual violation for this lineup."
                )
                break

            new_lu = catalog[j]
            new_lt = cat_tuples[j]
            entrants[i2] = new_lu
            idxs_by_lineup[new_lt].append(i2)
            counts[new_lt] += 1

    return cap_abs


def _features(
    lu: list[tuple[str, str]],
    pool: dict[str, dict],
    chalk_threshold: float,
    ownership_floor: float,
):
    proj = sum(pool[p]["proj"] for _, p in lu)
    salary = sum(pool[p]["salary"] for _, p in lu)

    def logit_pct(pct: float) -> float:
        # clamp ownership to avoid logit explosions when feeds are sparse
        p = max(1e-4, min(0.9999, max(ownership_floor, pct) / 100.0))
        return math.log(p / (1 - p))

    own_logit_sum = sum(logit_pct(pool[p]["own"]) for _, p in lu)
    chalk_cnt = sum(1 for _, p in lu if pool[p]["own"] >= chalk_threshold)
    return proj, own_logit_sum, salary, chalk_cnt


def _popularities(
    catalog: list[list[tuple[str, str]]],
    pool: dict[str, dict],
    w: Weights,
    chalk_threshold: float,
    ownership_floor: float,
) -> list[float]:
    scores = []
    for lu in catalog:
        proj, own_logit, salary, chalk = _features(
            lu, pool, chalk_threshold=chalk_threshold, ownership_floor=ownership_floor
        )
        s = (
            w.bias
            + w.weight_proj * proj
            + w.weight_salary * salary
            + w.weight_own * own_logit
            + w.weight_chalk_cnt * chalk
        )
        scores.append(s)
    scores = np.asarray(scores, dtype=float)
    scores -= scores.max()
    exp_scores = np.exp(scores)
    total = float(exp_scores.sum())
    return (exp_scores / total).tolist()


def _load_bucket_targets(bucket_targets_path: str | None) -> list[BucketTarget]:
    """Load bucket targets from YAML file."""
    if not bucket_targets_path or not os.path.exists(bucket_targets_path):
        return []

    try:
        with open(bucket_targets_path) as f:
            data = yaml.safe_load(f)

        targets = []
        for item in data.get("bucket_targets", []):
            targets.append(
                BucketTarget(
                    run_id=item.get("run_id"),
                    salary_bin=item.get("salary_bin"),
                    ownership_tertile=item.get("ownership_tertile"),
                    target_share=float(item.get("target_share", 0.0)),
                )
            )
        return targets
    except Exception as e:
        print(f"[WARN] Failed to load bucket targets from {bucket_targets_path}: {e}")
        return []


def _categorize_lineup(
    lu: list[tuple[str, str]],
    pool: dict[str, dict],
    own_low: float | None = None,
    own_high: float | None = None,
) -> tuple[str, str]:
    """Categorize a lineup by salary bin and ownership tertile.
    If own_low/high are provided, they are quantile cut points for **sum** ownership; otherwise fallback to fixed thresholds.
    """
    total_salary = sum(pool[p]["salary"] for _, p in lu if p in pool)
    own_sum = sum(pool[p]["own"] for _, p in lu if p in pool)

    # Salary bins tuned to DK duplication clusters
    if total_salary >= 49800:
        salary_bin = "high"
    elif total_salary >= 49500:
        salary_bin = "mid"
    else:
        salary_bin = "low"

    if own_low is not None and own_high is not None:
        if own_sum <= own_low:
            ownership_tertile = "low_own"
        elif own_sum <= own_high:
            ownership_tertile = "mid_own"
        else:
            ownership_tertile = "high_own"
    else:
        # Fallback fixed thresholds on **average** own (legacy behavior)
        avg_own = own_sum / max(1, len(lu))
        if avg_own < 10.0:
            ownership_tertile = "low_own"
        elif avg_own >= 25.0:
            ownership_tertile = "high_own"
        else:
            ownership_tertile = "mid_own"

    return salary_bin, ownership_tertile


def _bucket_sampling_with_targets(
    catalog: list[list[tuple[str, str]]],
    pool: dict[str, dict],
    p: list[float],
    field_size: int,
    bucket_targets: list[BucketTarget],
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, float]]:
    """Apply bucketed sampling to honor target shares within ±2%.
    Buckets are defined over (salary_bin × ownership_tertile). Realized shares are
    computed from the final counts rather than assumed from targets.
    """
    # No targets → classic multinomial
    if not bucket_targets:
        counts = rng.multinomial(field_size, p)
        return counts, {}

    # Data-driven ownership tertiles from catalog **sum** ownership
    own_sums = [sum(pool[pid]["own"] for _, pid in lu if pid in pool) for lu in catalog]
    if len(own_sums) >= 3 and np.any(np.isfinite(own_sums)):
        low_t, high_t = np.quantile(own_sums, [1 / 3, 2 / 3])
    else:
        low_t, high_t = (None, None)

    # Categorize catalog lineups into buckets
    lineup_buckets: dict[int, str] = {}
    bucket_lineups: dict[str, list[int]] = defaultdict(list)
    for i, lu in enumerate(catalog):
        sb, ot = _categorize_lineup(lu, pool, low_t, high_t)
        key = f"{sb}_{ot}"
        lineup_buckets[i] = key
        bucket_lineups[key].append(i)

    # Build integer target counts per bucket
    target_counts: dict[str, int] = {}
    total_target_share = 0.0
    for t in bucket_targets:
        if t.salary_bin and t.ownership_tertile:
            key = f"{t.salary_bin}_{t.ownership_tertile}"
            target_counts[key] = int(field_size * float(t.target_share))
            total_target_share += float(t.target_share)

    # Normalize if targets don't sum to 1.0 (warn on large drift)
    if target_counts:
        total_alloc = sum(target_counts.values())
        if total_alloc != field_size:
            if abs(total_target_share - 1.0) > 0.02:
                print(
                    f"[WARN] bucket target shares sum to {total_target_share:.3f}; normalizing to 1.0"
                )
            scale = field_size / max(1, total_alloc)
            target_counts = {k: int(round(v * scale)) for k, v in target_counts.items()}

    # Sample within each bucket by renormalized p
    counts = np.zeros(len(catalog), dtype=int)
    p_arr = np.asarray(p, dtype=float)
    p_arr /= p_arr.sum()
    allocated = 0
    for key, need in target_counts.items():
        idxs = bucket_lineups.get(key, [])
        if not idxs or need <= 0:
            continue
        sub_p = p_arr[idxs]
        s = sub_p.sum()
        if s > 0:
            sub_p = sub_p / s
            take = rng.multinomial(need, sub_p)
            for off, idx in enumerate(idxs):
                c = int(take[off])
                if c:
                    counts[idx] += c
            allocated += int(need)

    # Backfill any shortfall by global p
    short = field_size - allocated
    if short > 0:
        back = rng.multinomial(short, p_arr)
        counts += back

    # Compute realized shares from final counts
    bucket_totals: dict[str, int] = Counter()
    for idx, c in enumerate(counts):
        if c:
            bucket_totals[lineup_buckets[idx]] += int(c)
    realized = {k: v / float(field_size) for k, v in bucket_totals.items()}
    return counts, realized


# Insert stable lineup signature helper above _compute_gini_coefficient


def _lu_sig(lu: list[tuple[str, str]]) -> str:
    """Stable signature for a lineup: MD5 over DK slot-ordered player IDs."""
    order = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    row = {s: p for s, p in lu}
    sig = ",".join(row.get(s, "") for s in order)
    return hashlib.md5(sig.encode("utf-8")).hexdigest()[:12]


def _compute_gini_coefficient(dup_counts: Counter) -> float:
    """Compute Gini coefficient for duplicate distribution."""
    if not dup_counts:
        return 0.0

    counts = sorted(dup_counts.values())
    n = len(counts)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * counts)) / (n * np.sum(counts)) - (n + 1) / n


def _compute_player_exposures(
    entrants: list[list[tuple[str, str]]],
) -> dict[str, float]:
    """Compute player exposure percentages."""
    player_counts = Counter()
    total_lineups = len(entrants)

    for lu in entrants:
        for _, pid in lu:
            player_counts[pid] += 1

    return {
        pid: (count / total_lineups) * 100.0 for pid, count in player_counts.items()
    }


def _apply_salary_window(catalog, pool, min_sal: int | None, max_sal: int | None):
    if min_sal is None and max_sal is None:
        return catalog
    out = []
    for lu in catalog:
        # Handle slot-aware lineups: extract player IDs from (slot, player_id) tuples
        sal = sum(pool[p]["salary"] for _, p in lu)
        if (min_sal is None or sal >= min_sal) and (max_sal is None or sal <= max_sal):
            out.append(lu)
    return out


def _cap_counts_pct(counts: np.ndarray, cap_abs: int | None) -> np.ndarray:
    if cap_abs is None:
        return counts
    counts = counts.astype(int).copy()
    total = counts.sum()
    # First clamp
    over_mask = counts > cap_abs
    excess = int(counts[over_mask].sum() - cap_abs * over_mask.sum())
    counts[over_mask] = cap_abs
    # Redistribute excess only into bins strictly below cap_abs
    if excess > 0:
        under_idx = np.where(counts < cap_abs)[0].tolist()
        i = 0
        while excess > 0 and under_idx:
            j = under_idx[i % len(under_idx)]
            counts[j] += 1
            if counts[j] == cap_abs:
                # remove now-capped index
                under_idx.pop(i % len(under_idx))
                i = i % (len(under_idx) if under_idx else 1)
            else:
                i += 1
    # As a final guard, if total changed due to rounding, adjust uniformly
    diff = counts.sum() - total
    if diff != 0:
        sign = -1 if diff > 0 else +1
        adjustable = np.where((counts > 0) if diff > 0 else (counts < cap_abs))[0]
        k = 0
        for _ in range(abs(diff)):
            if not len(adjustable):
                break
            idx = adjustable[k % len(adjustable)]
            counts[idx] += sign
            k += 1
    return counts


def build_field_with_replacement(
    catalog_path: str,
    player_pool_path: str,
    your_entries_path: str | None,
    contest_size: int,
    entrants_path: str,
    live_path: str,
    dup_mode: str = "multinomial",
    weights: Weights | None = None,
    random_seed: int = 23,
    min_salary: int | None = None,
    max_salary: int | None = None,
    sport: str = "NBA_CLASSIC",
    max_dup_cap_pct: float | None = None,
    chalk_threshold: float = 30.0,
    ownership_floor: float = 2.0,
    bucket_targets_path: str | None = None,
    exposures_csv_path: str | None = None,
    report_json_path: str | None = None,
    inject_full_catalog: bool = True,
) -> dict:
    # Ensure weights is initialized
    if weights is None:
        weights = Weights()

    # Validate dup_mode
    if dup_mode not in {"multinomial", "uniform"}:
        raise ValueError(
            f"dup_mode must be 'multinomial' or 'uniform', got '{dup_mode}'"
        )

    # Resolve directory inputs to actual file paths if needed
    catalog_path = _resolve_catalog_path(catalog_path)
    player_pool_path = _resolve_pool_path(player_pool_path)
    print(
        f"[FIELD] catalog={catalog_path} pool={player_pool_path} yours={your_entries_path or 'NONE'} contest_size={contest_size} seed={random_seed} inject_full_catalog={inject_full_catalog}"
    )
    rng = np.random.default_rng(random_seed)
    pool = _read_pool(player_pool_path)
    catalog = _read_long(catalog_path)  # list[list[(slot, pid)]]
    # PID overlap diagnostics
    cat_pids = {p for lu in catalog for _, p in lu}
    pool_pids = set(pool.keys())
    overlap = len(cat_pids & pool_pids)
    if overlap == 0:
        print(
            f"[WARN] No overlap between catalog PIDs ({len(cat_pids)}) and pool PIDs ({len(pool_pids)}). Check ID columns."
        )
    else:
        missing_set = cat_pids - pool_pids
        missing = list(missing_set)[:5]
        print(
            f"[FIELD] PID overlap: {overlap}/{len(cat_pids)} (pool_unique={len(pool_pids)}); sample missing: {missing}"
        )
        if missing and any(
            isinstance(x, str) and x.endswith(".0") for x in list(missing_set)[:10]
        ):
            print(
                "[HINT] Some catalog PIDs end with '.0'. Normalizing PIDs; if you still see this, check pool ID column."
            )
        if overlap / max(1, len(cat_pids)) < 0.6:
            print(
                "[WARN] Low catalog↔pool PID overlap (<60%). Ensure both files are from the SAME run and DK ID space."
            )
    # If UI passed the catalog as your_entries, ignore to avoid duplication
    if your_entries_path and os.path.exists(your_entries_path):
        try:
            same = os.path.samefile(your_entries_path, catalog_path)
        except Exception:
            same = os.path.abspath(your_entries_path) == os.path.abspath(catalog_path)
        if same:
            print("[INFO] your_entries path equals catalog; ignoring your_entries.")
            your_entries_path = None
    # Treat missing or non-existent path as NO_ENTRIES mode
    if your_entries_path and os.path.exists(your_entries_path):
        yours = _read_long(your_entries_path)
    else:
        if your_entries_path and not os.path.exists(your_entries_path):
            print(
                f"[INFO] your_entries not found at {your_entries_path}; running NO_ENTRIES mode."
            )
        yours = []
    _validate_catalog(catalog, pool, "catalog")
    if yours:
        _validate_catalog(yours, pool, "your_entries")
        _validate_lineup_shape(yours, pool, "your_entries")
        _validate_salary_cap(yours, pool, sport, "your_entries")
        _validate_slot_eligibility(yours, pool, "your_entries")
    _validate_lineup_shape(catalog, pool, "catalog")
    _validate_salary_cap(catalog, pool, sport, "catalog")
    _validate_slot_eligibility(catalog, pool, "catalog")

    # Basic validations
    n_you = len(yours)
    n_catalog = len(catalog)

    # Implement full catalog injection validation
    if inject_full_catalog:
        if contest_size < n_you + n_catalog:
            raise ValueError(
                f"inject_full_catalog=True requires contest_size >= n_you + n_catalog "
                f"({contest_size} < {n_you} + {n_catalog}). Increase contest_size or disable full-catalog injection."
            )

    if not inject_full_catalog and n_you <= 0:
        raise ValueError(
            "your_entries_path is empty or None, and inject_full_catalog=False"
        )

    field_size = contest_size - n_you
    if not inject_full_catalog and field_size <= 0:
        raise ValueError("contest_size must exceed your entries")

    # Apply salary window filter
    catalog = _apply_salary_window(catalog, pool, min_salary, max_salary)

    if not catalog:
        raise ValueError("No eligible catalog lineups after salary filters")

    # Ownership coverage note (model still works via ownership_floor clamp)
    own_vals = [pool[p]["own"] for lu in catalog for _, p in lu if p in pool]
    zero_own_ratio = float(sum(1 for v in own_vals if v <= 0.0)) / max(1, len(own_vals))
    notes: list[str] = []
    if zero_own_ratio >= 0.25:
        notes.append(
            f"Ownership sparse: {zero_own_ratio:.0%} of used player ownerships are ≤ 0.0. "
            f"Using ownership_floor={ownership_floor}% in popularity model."
        )

    # Popularities (slot-aware + tunable knobs)
    p = _popularities(
        catalog=catalog,
        pool=pool,
        w=weights,
        chalk_threshold=chalk_threshold,
        ownership_floor=ownership_floor,
    )
    if dup_mode == "uniform":
        p = [1.0 / len(catalog)] * len(catalog)

    # Load bucket targets
    bucket_targets = _load_bucket_targets(bucket_targets_path)

    # Determine field building strategy and protected prefix size
    if inject_full_catalog:
        # Full catalog injection mode
        # 1) Start entrants with YOUR entries at the front
        entrants = list(yours)

        # 2) Append exactly one copy of every catalog lineup (coverage block)
        entrants.extend(catalog)

        # 3) Fill remaining seats by sampling with replacement using p (or bucketed p)
        covered = len(entrants)
        remaining = contest_size - covered
        protected_prefix_n = n_you + n_catalog

        if remaining > 0:
            # Handle bucketed sampling for remaining seats only
            counts, realized_shares = _bucket_sampling_with_targets(
                catalog, pool, p, remaining, bucket_targets, rng
            )

            # Expand remaining seats based on counts
            for idx, k in enumerate(counts):
                if k:
                    entrants.extend([catalog[idx]] * int(k))
        else:
            # No remaining seats to fill
            counts = np.zeros(n_catalog, dtype=int)
            realized_shares = {}
    else:
        # Original logic: sample replacement field then inject your entries
        counts, realized_shares = _bucket_sampling_with_targets(
            catalog, pool, p, field_size, bucket_targets, rng
        )

        # Cap by % of field (sport default if pct not provided)
        cap_pct = max_dup_cap_pct
        if cap_pct is None:
            cap_pct = SPORT_DEFAULT_CAP.get(sport.upper(), None)
        cap_abs = None
        original_cap_abs = None
        if cap_pct is not None:
            cap_abs = max(
                1, int(math.floor(contest_size * cap_pct))
            )  # clamp to at least 1
            original_cap_abs = cap_abs
        counts = _cap_counts_pct(counts, cap_abs)

        # Expand to field
        field: list[list[tuple[str, str]]] = []
        for idx, k in enumerate(counts):
            if k:
                field.extend([catalog[idx]] * int(k))

        # Edge case: ensure field long enough to replace
        if len(field) < n_you:
            additional_needed = n_you - len(field)
            p_arr = np.asarray(p, dtype=float)
            p_arr /= p_arr.sum()
            additional_indices = rng.choice(
                len(catalog), size=additional_needed, p=p_arr
            )
            field.extend([catalog[i] for i in additional_indices])

        # Inject your entries by replacement
        if n_you > 0:
            replace_indices = rng.choice(len(field), size=n_you, replace=False)
            for i, lu in enumerate(yours):
                field[int(replace_indices[i])] = lu

            # Build final entrants list: your entries + remaining field
            replace_idx_set = set(int(x) for x in replace_indices)
            remaining_field = [
                lu for j, lu in enumerate(field) if j not in replace_idx_set
            ]
            entrants = yours + remaining_field
        else:
            entrants = field

        protected_prefix_n = n_you

    # Cap by % of field (sport default if pct not provided) - only for non-full-catalog mode
    cap_pct = max_dup_cap_pct
    if cap_pct is None:
        cap_pct = SPORT_DEFAULT_CAP.get(sport.upper(), None)
    cap_abs = None
    original_cap_abs = None
    if cap_pct is not None and not inject_full_catalog:
        cap_abs = max(1, int(math.floor(contest_size * cap_pct)))  # clamp to at least 1
        original_cap_abs = cap_abs
    elif cap_pct is not None and inject_full_catalog:
        # For full catalog injection, apply cap to duplicate portions only
        cap_abs = max(1, int(math.floor(contest_size * cap_pct)))
        original_cap_abs = cap_abs

    # Ensure exact contest_size
    if len(entrants) != contest_size:
        if len(entrants) < contest_size:
            needed = contest_size - len(entrants)
            p_arr = np.asarray(p, dtype=float)
            p_arr /= p_arr.sum()
            extra_idx = rng.choice(len(catalog), size=needed, p=p_arr)
            entrants.extend([catalog[i] for i in extra_idx])
        else:
            entrants = entrants[:contest_size]

    # Post-inject duplicate cap enforcement (robust, non-violating)
    final_cap_abs = _enforce_dup_cap_inplace(
        entrants, catalog, p, dup_mode, rng, protected_prefix_n, cap_abs
    )

    # Assert length before writes
    assert len(entrants) == contest_size, "Entrants length mismatch"

    # Write outputs (slot-aware long)
    _write_long(entrants, entrants_path)
    _write_long(entrants, live_path)

    # Write UI copy (with header)
    try:
        _write_tournament_wide(entrants, str(paths.TOURNAMENT_LINEUPS))
    except Exception as e:
        print(f"[WARN] Failed to write tournament_lineups.csv (UI): {e}")

    # Write simulator copy (no header)
    sim_tournament_lineups_path = None
    try:
        sim_path = os.path.join(str(paths.DK_DATA), "tournament_lineups.csv")
        _write_simulator_tournament_wide(entrants, sim_path)
        sim_tournament_lineups_path = sim_path
    except Exception as e:
        print(f"[WARN] Failed to write simulator tournament_lineups.csv: {e}")

    # Duplication stats
    dup_counts = Counter(tuple(lu) for lu in entrants)
    hist = Counter(dup_counts.values())

    # Compute expanded telemetry
    gini_coeff = _compute_gini_coefficient(dup_counts)
    player_exposures = _compute_player_exposures(entrants)
    top_dupes = [(_lu_sig(list(lu)), count) for lu, count in dup_counts.most_common(10)]

    # Compute bucket deviation if targets were provided
    bucket_deviation = 0.0
    if bucket_targets and realized_shares:
        target_shares = {
            f"{t.salary_bin}_{t.ownership_tertile}": t.target_share
            for t in bucket_targets
            if t.salary_bin and t.ownership_tertile
        }
        deviations = [
            abs(realized_shares.get(k, 0.0) - target_shares.get(k, 0.0))
            for k in set(target_shares.keys()) | set(realized_shares.keys())
        ]
        bucket_deviation = max(deviations) if deviations else 0.0

    # Quick analytics for UI
    try:
        salaries = [sum(pool[p]["salary"] for _, p in lu) for lu in entrants]
        proj_sum = [sum(pool[p]["proj"] for _, p in lu) for lu in entrants]
        salary_min = min(salaries) if salaries else None
        salary_max = max(salaries) if salaries else None
        salary_mean = float(np.mean(salaries)) if salaries else None
        proj_mean = float(np.mean(proj_sum)) if proj_sum else None
        proj_std = float(np.std(proj_sum)) if proj_sum else None
    except Exception:
        salary_min = salary_max = salary_mean = proj_mean = proj_std = None

    # Write exposures CSV if requested
    if exposures_csv_path and player_exposures:
        try:
            exposures_dir = os.path.dirname(exposures_csv_path) or "."
            os.makedirs(exposures_dir, exist_ok=True)
            with open(exposures_csv_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["player_id", "exposure_pct"])
                for pid, exposure in sorted(player_exposures.items()):
                    w.writerow([pid, f"{exposure:.2f}"])
        except Exception as e:
            print(f"[WARN] Failed to write player exposures CSV: {e}")

    # Determine telemetry mode
    mode = (
        "FULL_CATALOG_INJECTION"
        if inject_full_catalog
        else ("INJECT_ENTRIES" if n_you > 0 else "NO_ENTRIES")
    )

    # Persist run_meta.json with telemetry data
    meta = {
        "random_seed": random_seed,
        "contest_size": contest_size,
        "n_catalog": len(catalog),
        "n_you": n_you,
        "mode": mode,
        "coverage_block": n_catalog if inject_full_catalog else 0,
        "dup_histogram": dict(sorted(hist.items())),
        "cap_pct": cap_pct,
        "cap_abs": cap_abs,
        "cap_relaxed_to": final_cap_abs if original_cap_abs != final_cap_abs else None,
        "sim_tournament_lineups": sim_tournament_lineups_path,
        "chalk_threshold": chalk_threshold,
        "ownership_floor": ownership_floor,
        "dup_mode": dup_mode,
        "salary_min": salary_min,
        "salary_mean": salary_mean,
        "salary_max": salary_max,
        "proj_mean": proj_mean,
        "proj_std": proj_std,
        "notes": notes,
        # Expanded telemetry (PRP-FS-05)
        "bucket_targets": (
            [
                {
                    "salary_bin": t.salary_bin,
                    "ownership_tertile": t.ownership_tertile,
                    "target_share": t.target_share,
                }
                for t in bucket_targets
            ]
            if bucket_targets
            else []
        ),
        "realized_bucket_shares": realized_shares,
        "bucket_deviation": bucket_deviation,
        "gini_coefficient": gini_coeff,
        "top_dupes": top_dupes,
        "player_exposures_count": len(player_exposures),
    }
    meta_path = os.path.join(os.path.dirname(entrants_path) or ".", "run_meta.json")
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=2)

    # Write separate report JSON if requested
    if report_json_path:
        try:
            report_dir = os.path.dirname(report_json_path) or "."
            os.makedirs(report_dir, exist_ok=True)
            with open(report_json_path, "w") as fh:
                json.dump(meta, fh, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write report JSON: {e}")

    return {
        "ok": True,
        "contest_size": contest_size,
        "n_catalog": len(catalog),
        "n_you": n_you,
        "mode": mode,
        "coverage_block": n_catalog if inject_full_catalog else 0,
        "unique_in_entrants": sum(1 for k in dup_counts.values() if k == 1),
        "max_dupes": max(dup_counts.values()) if dup_counts else 0,
        "dup_histogram": dict(sorted(hist.items())),
        "out_path": entrants_path,
        "live_path": live_path,
        "cap_pct": cap_pct,
        "cap_abs": cap_abs,
        "cap_relaxed_to": final_cap_abs if original_cap_abs != final_cap_abs else None,
        "sim_tournament_lineups": sim_tournament_lineups_path,
        "chalk_threshold": chalk_threshold,
        "ownership_floor": ownership_floor,
        "dup_mode": dup_mode,
        "salary_min": salary_min,
        "salary_mean": salary_mean,
        "salary_max": salary_max,
        "proj_mean": proj_mean,
        "proj_std": proj_std,
        "notes": notes,
        # Expanded telemetry (PRP-FS-05)
        "bucket_targets": [
            {
                "run_id": t.run_id,
                "salary_bin": t.salary_bin,
                "ownership_tertile": t.ownership_tertile,
                "target_share": t.target_share,
            }
            for t in bucket_targets
        ],
        "realized_bucket_shares": realized_shares,
        "bucket_deviation": bucket_deviation,
        "gini_coefficient": gini_coeff,
        "top_dupes": top_dupes,
        "player_exposures": player_exposures,
    }


# Legacy compatibility function
def build_field(
    catalog_path: str = str(paths.VARIANT_CATALOG),
    player_pool_path: str = str(paths.PLAYER_POOL),
    your_entries_path: str | None = None,
    contest_size: int = 100,
    out_path: str = str(paths.DK_DATA / "entrants.csv"),
    random_seed: int = 13,
):
    """Legacy compatibility wrapper for build_field_with_replacement"""
    live_path = str(paths.LIVE_LINEUPS)
    return build_field_with_replacement(
        catalog_path=catalog_path,
        player_pool_path=player_pool_path,
        your_entries_path=None,
        contest_size=contest_size,
        entrants_path=out_path,
        live_path=live_path,
        random_seed=random_seed,
        inject_full_catalog=True,
    )


# CLI entrypoint
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument(
        "--yours", default=None, help="Path to your entries CSV file (optional)"
    )
    ap.add_argument("--contest_size", type=int, required=True)
    ap.add_argument("--entrants", required=True)
    ap.add_argument("--live", required=True)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--min_salary", type=int, default=None)
    ap.add_argument("--max_salary", type=int, default=None)
    ap.add_argument(
        "--dup_mode", default="multinomial", choices=["multinomial", "uniform"]
    )
    ap.add_argument("--sport", default="NBA_CLASSIC")
    ap.add_argument("--max_dup_cap_pct", type=float, default=None)
    ap.add_argument("--chalk_threshold", type=float, default=30.0)
    ap.add_argument("--ownership_floor", type=float, default=2.0)
    ap.add_argument(
        "--bucket_targets", default=None, help="Path to bucket targets YAML file"
    )
    ap.add_argument(
        "--exposures_csv", default=None, help="Path to write player exposures CSV"
    )
    ap.add_argument(
        "--report_json", default=None, help="Path to write detailed report JSON"
    )
    ap.add_argument(
        "--inject_full_catalog",
        action="store_true",
        default=True,
        help="Guarantee full catalog injection (each lineup at least once)",
    )
    args = ap.parse_args()
    # Resolve directory or file for catalog/pool
    cat_path = _resolve_catalog_path(args.catalog)
    pool_path = _resolve_pool_path(args.pool)
    # Normalize --yours: treat empty string or missing file as None
    yours_path = args.yours
    if not yours_path or (
        isinstance(yours_path, str) and not os.path.exists(yours_path)
    ):
        if yours_path:
            print(
                f"[INFO] --yours provided but file not found at {yours_path}; proceeding without your entries."
            )
        yours_path = None
    build_field_with_replacement(
        catalog_path=cat_path,
        player_pool_path=pool_path,
        your_entries_path=yours_path,
        contest_size=args.contest_size,
        entrants_path=args.entrants,
        live_path=args.live,
        random_seed=args.seed,
        min_salary=args.min_salary,
        max_salary=args.max_salary,
        dup_mode=args.dup_mode,
        sport=args.sport,
        max_dup_cap_pct=args.max_dup_cap_pct,
        chalk_threshold=args.chalk_threshold,
        ownership_floor=args.ownership_floor,
        bucket_targets_path=args.bucket_targets,
        exposures_csv_path=args.exposures_csv,
        report_json_path=args.report_json,
        inject_full_catalog=args.inject_full_catalog,
    )
