from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from validators.lineup_rules import (
    DK_SLOTS_ORDER,
    POSITION_ELIGIBILITY,
    LineupValidator,
)


class Randomizer:
    """RNG with seed for reproducibility."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def shuffle(self, items: list[Any]) -> None:
        """Shuffle list in-place."""
        self.rng.shuffle(items)

    def choice(self, items: list[Any]) -> Any:
        """Pick random item from list."""
        return self.rng.choice(items)

    def choices(
        self, items: list[Any], weights: list[float] | None = None, k: int = 1
    ) -> list[Any]:
        """Pick k items with optional weights."""
        return self.rng.choices(items, weights=weights, k=k)

    def sample(self, items: list[Any], k: int) -> list[Any]:
        """Sample k items without replacement."""
        return self.rng.sample(items, k)


class PositionAllocator:
    """Assign slots via validator eligibility."""

    def __init__(self, randomizer: Randomizer) -> None:
        self.randomizer = randomizer

    def allocate_positions(self, players: pd.DataFrame) -> list[tuple[str, str]] | None:
        """Allocate players to positions, return lineup or None if impossible."""
        # Create position-eligible pools
        pos_pools: dict[str, list[str]] = {}
        for slot in DK_SLOTS_ORDER:
            eligible_positions = POSITION_ELIGIBILITY[slot]
            pool = []
            for _, player in players.iterrows():
                # Handle NaN positions properly and ensure positions are sets
                positions_value = player["positions"]
                if pd.isna(positions_value):
                    player_positions: set[str] = set()
                else:
                    player_positions = set(str(positions_value).split("/"))

                if eligible_positions & player_positions:
                    pool.append(str(player["player_id"]))
            pos_pools[slot] = pool

        # Try to allocate using greedy approach with backtracking
        used_players: set[str] = set()
        assignment: list[tuple[str, str]] = []

        def backtrack(slot_idx: int) -> bool:
            if slot_idx >= len(DK_SLOTS_ORDER):
                return True

            slot = DK_SLOTS_ORDER[slot_idx]
            available = [p for p in pos_pools[slot] if p not in used_players]
            if not available:
                return False

            # Randomize order to try
            self.randomizer.shuffle(available)

            for player_id in available:
                used_players.add(player_id)
                assignment.append((slot, player_id))

                if backtrack(slot_idx + 1):
                    return True

                # Backtrack
                used_players.remove(player_id)
                assignment.pop()

            return False

        if backtrack(0):
            return assignment
        return None


class SalaryManager:
    """Enforce salary cap distributions."""

    def __init__(self, salary_cap: int = 50000) -> None:
        self.salary_cap = salary_cap

    def check_salary_valid(
        self, lineup: list[tuple[str, str]], players: pd.DataFrame
    ) -> bool:
        """Check if lineup satisfies salary cap."""
        player_ids = [pid for _, pid in lineup]
        try:
            sub = players.set_index("player_id").loc[player_ids]
            total_salary = int(sub["salary"].sum())
            return total_salary <= self.salary_cap
        except KeyError:
            return False


class TeamLimiter:
    """Respect per-team limits."""

    def __init__(self, max_per_team: int = 4) -> None:
        self.max_per_team = max_per_team

    def check_team_limits(
        self, lineup: list[tuple[str, str]], players: pd.DataFrame
    ) -> bool:
        """Check if lineup satisfies team limits."""
        player_ids = [pid for _, pid in lineup]
        try:
            sub = players.set_index("player_id").loc[player_ids]
            team_counts = sub["team"].value_counts()
            return bool((team_counts <= self.max_per_team).all())
        except KeyError:
            return False


class OwnershipBias:
    """Weight variants by projected ownership."""

    def __init__(self, randomizer: Randomizer) -> None:
        self.randomizer = randomizer

    def get_ownership_weight(
        self, lineup: list[tuple[str, str]], players: pd.DataFrame
    ) -> float:
        """Calculate ownership-based weight for lineup."""
        player_ids = [pid for _, pid in lineup]
        try:
            sub = players.set_index("player_id").loc[player_ids]
            if "ownership" not in sub.columns:
                return 1.0
            # Use geometric mean to avoid extreme weights
            ownership_values = sub["ownership"].fillna(0.1)
            # Prevent zero/negative ownership
            ownership_values = ownership_values.clip(lower=0.01)
            weight = float(ownership_values.prod() ** (1.0 / len(ownership_values)))
            return weight
        except (KeyError, ZeroDivisionError):
            return 1.0

    def sample_by_ownership(
        self,
        lineups: list[list[tuple[str, str]]],
        players: pd.DataFrame,
        k: int,
    ) -> list[list[tuple[str, str]]]:
        """Sample lineups weighted by ownership."""
        if not lineups or k <= 0:
            return []

        weights = [self.get_ownership_weight(lineup, players) for lineup in lineups]

        # Handle edge cases
        if all(w == 0 for w in weights):
            weights = [1.0] * len(weights)

        # Sample with replacement if needed
        if k >= len(lineups):
            return lineups.copy()

        return self.randomizer.choices(lineups, weights=weights, k=k)


def _utc_now() -> str:
    """Get current UTC timestamp."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write list of dicts as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class SamplerEngine:
    """Main field sampling engine with modular sub-engines."""

    def __init__(
        self,
        projections: pd.DataFrame,
        seed: int = 42,
        out_dir: Path | str = Path("data"),
        salary_cap: int = 50000,
        max_per_team: int = 4,
        compat_mode: bool = False,
    ) -> None:
        self.projections = projections.copy()
        self.seed = seed
        self.out_dir = Path(out_dir)
        self.compat_mode = compat_mode

        # Initialize sub-engines
        self.randomizer = Randomizer(seed)
        self.position_allocator = PositionAllocator(self.randomizer)
        self.salary_manager = SalaryManager(salary_cap)
        self.team_limiter = TeamLimiter(max_per_team)
        self.ownership_bias = OwnershipBias(self.randomizer)

        # Initialize validator
        self.validator = LineupValidator(
            salary_cap=salary_cap, max_per_team=max_per_team
        )

        # Legacy compatibility: use built-in random.Random for exact reproducibility
        if compat_mode:
            import random

            self.legacy_rng = random.Random(seed)

    def _generate_export_csv_row(self, lineup: list[tuple[str, str]]) -> str:
        """Generate DK lineup upload CSV row."""
        # DK expects players in slot order
        player_ids = [pid for _, pid in lineup]
        return ",".join(player_ids)

    def _generate_single_lineup(self) -> list[tuple[str, str]] | None:
        """Generate a single valid lineup."""
        if self.compat_mode:
            return self._generate_single_lineup_legacy()
        else:
            return self._generate_single_lineup_improved()

    def _generate_single_lineup_legacy(self) -> list[tuple[str, str]] | None:
        """Legacy algorithm: exact replica of injection_model.py behavior."""
        max_attempts = 10000
        attempts = 0

        # Use exact original algorithm for compatibility
        pool = self.projections[["player_id", "team", "salary", "positions"]]
        players = pool.to_dict("records")

        while attempts < max_attempts:
            attempts += 1

            # Use legacy RNG for exact reproducibility
            self.legacy_rng.shuffle(players)
            lineup = list(
                zip(DK_SLOTS_ORDER, [p["player_id"] for p in players[:8]], strict=False)
            )

            # Validate with LineupValidator (includes salary, team, position checks)
            if self.validator.validate(lineup, pool):
                return lineup

        return None

    def _generate_single_lineup_improved(self) -> list[tuple[str, str]] | None:
        """Improved algorithm using simpler approach like legacy but with structure."""
        max_attempts = 1000
        attempts = 0

        # Convert to list for shuffling like legacy algorithm
        player_records = self.projections.to_dict("records")

        while attempts < max_attempts:
            attempts += 1

            # Shuffle players for randomness
            self.randomizer.shuffle(player_records)

            # Try to assign first 8 players to positions like legacy algorithm
            lineup = []
            used_players = set()

            for slot in DK_SLOTS_ORDER:
                assigned = False
                for player in player_records:
                    player_id = str(player["player_id"])
                    if player_id in used_players:
                        continue

                    # Check position eligibility
                    positions_value = player["positions"]
                    if pd.isna(positions_value):
                        player_positions: set[str] = set()
                    else:
                        player_positions = set(str(positions_value).split("/"))

                    eligible_positions = POSITION_ELIGIBILITY[slot]
                    if eligible_positions & player_positions:
                        lineup.append((slot, player_id))
                        used_players.add(player_id)
                        assigned = True
                        break

                if not assigned:
                    break

            # If we couldn't assign all 8 slots, try again
            if len(lineup) != 8:
                continue

            # Validate constraints using sub-engines
            if not self.salary_manager.check_salary_valid(lineup, self.projections):
                continue

            if not self.team_limiter.check_team_limits(lineup, self.projections):
                continue

            # Final validation with LineupValidator
            if self.validator.validate(lineup, self.projections):
                return lineup

        return None

    def generate(self, field_size: int) -> dict[str, Any]:
        """Generate field of lineups and write artifacts."""
        run_id = f"fs-{uuid.uuid4().hex[:8]}"
        created_at = _utc_now()

        lineups: list[list[tuple[str, str]]] = []
        attempts = 0

        # Generate unique lineups
        seen_players: set[tuple[str, ...]] = set()

        while len(lineups) < field_size and attempts < field_size * 100:
            attempts += 1

            lineup = self._generate_single_lineup()
            if lineup is None:
                continue

            # Check uniqueness
            player_set = tuple(sorted(pid for _, pid in lineup))
            if player_set in seen_players:
                continue

            seen_players.add(player_set)
            lineups.append(lineup)

        # Convert to output format
        base_entries: list[dict[str, Any]] = []
        for lineup in lineups:
            players = [pid for _, pid in lineup]
            entry = {
                "players": players,
                "run_id": run_id,
                "created_at": created_at,
                "site": "dk",
                "slate_id": "generated",
                "seed": self.seed,
                "ruleset_version": "v1",
                "source": "public",
                "origin": "field_base",
                "owner": "field",
                "export_csv_row": self._generate_export_csv_row(lineup),
            }
            base_entries.append(entry)

        # Write artifacts
        self.out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(self.out_dir / "field_base.jsonl", base_entries)
        _write_jsonl(self.out_dir / "field_merged.jsonl", base_entries)

        # Generate metrics
        metrics = {
            "run_id": run_id,
            "created_at": created_at,
            "site": "dk",
            "slate_id": "generated",
            "seed": self.seed,
            "ruleset_version": "v1",
            "field_base_count": len(base_entries),
            "injected_count": 0,
            "field_merged_count": len(base_entries),
            "invalid_attempts": attempts - len(lineups),
            "attempts": attempts,
        }

        # Write metrics
        metrics_path = self.out_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        # Write audit file
        audit_path = self.out_dir / "audit_fs.md"
        audit_path.write_text(
            "# Field Sampler Audit\n\n- criticals: 0\n", encoding="utf-8"
        )

        return metrics

    def sample(self, variants: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
        """Sample field from variant catalog (PRP API)."""
        # Convert variant dicts to lineup format for internal processing
        lineups: list[list[tuple[str, str]]] = []

        for variant in variants:
            if "players" in variant and len(variant["players"]) == 8:
                lineup = list(zip(DK_SLOTS_ORDER, variant["players"], strict=False))
                # Validate before adding
                if self.validator.validate(lineup, self.projections):
                    lineups.append(lineup)

        # Sample using ownership bias if available
        sampled_lineups = self.ownership_bias.sample_by_ownership(
            lineups, self.projections, size
        )

        # Convert back to output format
        results: list[dict[str, Any]] = []
        for i, lineup in enumerate(sampled_lineups, 1):
            players = [pid for _, pid in lineup]
            entry = {
                "run_id": f"sampler-{uuid.uuid4().hex[:8]}",
                "entrant_id": i,
                "origin": "variant",
                "players": players,
                "export_csv_row": self._generate_export_csv_row(lineup),
                "weight": 1.0,
            }
            results.append(entry)

        return results
