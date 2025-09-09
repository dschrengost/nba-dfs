from __future__ import annotations

import json
import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from validators.lineup_rules import (
    DK_SLOTS_ORDER,
    POSITION_ELIGIBILITY,
    LineupValidator,
)


@dataclass
class PositionAllocator:
    pool: pd.DataFrame

    def eligible(self, slot: str, taken: set[str]) -> pd.DataFrame:
        mask = ~self.pool["player_id"].isin(taken)
        subset = self.pool[mask]
        allowed = POSITION_ELIGIBILITY.get(slot, set())

        def check_position_eligibility(positions_value: Any) -> bool:
            if pd.isna(positions_value):
                return False
            player_positions = set(str(positions_value).split("/"))
            return bool(allowed & player_positions)

        elig_mask = subset["positions"].apply(check_position_eligibility)
        return subset[elig_mask]


@dataclass
class SalaryManager:
    remaining: int

    def can_afford(self, salary: int) -> bool:
        return salary <= self.remaining

    def add(self, salary: int) -> None:
        self.remaining -= salary


@dataclass
class TeamLimiter:
    max_per_team: int
    counts: dict[str, int] = field(default_factory=dict)

    def can_add(self, team: str) -> bool:
        return self.counts.get(team, 0) < self.max_per_team

    def add(self, team: str) -> None:
        self.counts[team] = self.counts.get(team, 0) + 1


@dataclass
class RejectionSampler:
    rng: random.Random
    allocator: PositionAllocator
    salary: SalaryManager
    teams: TeamLimiter

    def sample_lineup(self) -> list[str] | None:
        taken: set[str] = set()
        lineup: list[str] = []
        for slot in DK_SLOTS_ORDER:
            elig = self.allocator.eligible(slot, taken)
            if elig.empty:
                return None
            elig = elig[elig["salary"].apply(self.salary.can_afford)]
            elig = elig[elig["team"].apply(self.teams.can_add)]
            if elig.empty:
                return None
            weights = (
                elig["ownership"].astype(float).fillna(0.0).tolist()
                if "ownership" in elig.columns
                else [0.0] * len(elig)
            )
            if sum(weights) <= 0:
                weights = [1.0] * len(weights)
            player = self.rng.choices(elig["player_id"].tolist(), weights=weights, k=1)[
                0
            ]
            row = elig.set_index("player_id").loc[player]
            taken.add(player)
            self.salary.add(int(row["salary"]))
            self.teams.add(str(row["team"]))
            lineup.append(player)
        return lineup


@dataclass
class SamplerEngine:
    projections: pd.DataFrame
    seed: int
    salary_cap: int = 50000
    max_per_team: int = 4
    site: str = "dk"
    slate_id: str = ""
    out_dir: Path = Path("artifacts")

    def generate(self, n: int) -> dict[str, Any]:
        validator = LineupValidator(
            salary_cap=self.salary_cap, max_per_team=self.max_per_team
        )
        rng = random.Random(self.seed)
        allocator = PositionAllocator(self.projections)
        field: list[dict[str, Any]] = []
        attempts = 0
        while len(field) < n and attempts < n * 1000:
            attempts += 1
            salary = SalaryManager(self.salary_cap)
            teams = TeamLimiter(self.max_per_team)
            sampler = RejectionSampler(rng, allocator, salary, teams)
            lineup = sampler.sample_lineup()
            if lineup is None:
                continue
            if not validator.validate(
                list(zip(DK_SLOTS_ORDER, lineup, strict=False)), self.projections
            ):
                continue
            field.append({"players": lineup, "source": "public"})
        meta = self._write_outputs(field)
        meta["attempts"] = attempts
        meta["field_base_count"] = len(field)
        return meta

    def _write_outputs(self, field_data: Sequence[dict[str, Any]]) -> dict[str, Any]:
        self.out_dir.mkdir(exist_ok=True, parents=True)
        run_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        base_path = self.out_dir / "field_base.jsonl"
        with base_path.open("w", encoding="utf-8") as f:
            for row in field_data:
                f.write(json.dumps(row) + "\n")
        metrics = {
            "run_id": run_id,
            "created_at": created,
            "site": self.site,
            "slate_id": self.slate_id,
            "seed": self.seed,
            "ruleset_version": "1",
        }
        metrics_path = self.out_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return {
            "run_id": run_id,
            "field_path": str(base_path),
            "metrics_path": str(metrics_path),
            "created_at": created,
        }


def run_sampler(
    projections: pd.DataFrame, config: dict[str, Any], seed: int
) -> dict[str, Any]:
    eng = SamplerEngine(
        projections=projections,
        seed=seed,
        salary_cap=int(config.get("salary_cap", 50000)),
        max_per_team=int(config.get("max_per_team", 4)),
        site=str(config.get("site", "dk")),
        slate_id=str(config.get("slate_id", "")),
        out_dir=Path(config.get("out_dir", "artifacts")),
    )
    n = int(config.get("field_size", 1))
    return eng.generate(n)
