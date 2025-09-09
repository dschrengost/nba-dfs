from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SpecPlayer:
    player_id: str
    name: str
    team: str
    positions: list[str]
    salary: int
    proj: float
    dk_id: str | None = None
    own_proj: float | None = None


@dataclass
class Spec:
    site: str  # "dk" | "fd"
    roster_slots: list[str]
    salary_cap: int
    min_salary: int | None
    players: list[SpecPlayer]
    team_max: int | None = None
    team_limits: dict[str, int] | None = None
    lock_ids: list[str] | None = None
    ban_ids: list[str] | None = None
    lineup_size: int = 8
    N_lineups: int = 1
    unique_players: int = 0
    cp_sat_params: dict[str, Any] | None = None
    engine: str = "cp_sat"
    ownership_penalty: dict[str, Any] | None = None
