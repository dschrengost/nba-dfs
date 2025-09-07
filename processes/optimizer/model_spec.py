from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SpecPlayer:
    player_id: str
    name: str
    team: str
    positions: List[str]
    salary: int
    proj: float
    dk_id: Optional[str] = None
    own_proj: Optional[float] = None


@dataclass
class Spec:
    site: str  # "dk" | "fd"
    roster_slots: List[str]
    salary_cap: int
    min_salary: Optional[int]
    players: List[SpecPlayer]
    team_max: Optional[int] = None
    team_limits: Optional[Dict[str, int]] = None
    lock_ids: List[str] = None
    ban_ids: List[str] = None
    lineup_size: int = 8
    N_lineups: int = 1
    unique_players: int = 0
    cp_sat_params: Dict[str, Any] = None
    engine: str = "cp_sat"
    ownership_penalty: Optional[Dict[str, Any]] = None

