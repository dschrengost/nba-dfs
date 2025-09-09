from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

SiteType = Literal["dk", "fd"]


class ErrorCodes(str, Enum):
    INFEASIBLE = "INFEASIBLE"
    CONFIG_ERROR = "CONFIG_ERROR"
    MISSING_COLUMNS = "MISSING_COLUMNS"
    INVALID_PROJECTIONS = "INVALID_PROJECTIONS"
    SOLVER_TIMEOUT = "SOLVER_TIMEOUT"


class OptimizerError(Exception):
    def __init__(
        self,
        code: ErrorCodes,
        message: str,
        user_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.user_message = user_message or message
        self.details = details or {}


@dataclass
class OwnershipPenalty:
    enabled: bool = False
    # mode: "by_points" applies fixed lambda; "by_percent" searches lambda to reach % off-optimal
    mode: str = "by_points"
    weight_lambda: float = 0.0
    # curve settings
    curve_type: str = "sigmoid"  # linear|power|neglog|sigmoid
    power_k: float = 1.5
    pivot_p0: float = 0.20
    curve_alpha: float = 2.0
    clamp_min: float = 0.01
    clamp_max: float = 0.80
    shrink_gamma: float = 1.0
    # by_percent search knobs
    target_offoptimal_pct: float = 0.05
    tol_offoptimal_pct: float = 0.01

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> OwnershipPenalty | None:
        if not d:
            return None
        return cls(**{k: v for k, v in d.items() if k in cls().__dict__})


@dataclass
class Constraints:
    # high-level
    N_lineups: int = 1
    unique_players: int = 0
    # salary
    max_salary: int | None = None
    min_salary: int | None = None
    # teams
    global_team_limit: int | None = None
    team_limits: dict[str, int] = field(default_factory=dict)
    # player include/exclude
    lock_ids: list[str] = field(default_factory=list)
    ban_ids: list[str] = field(default_factory=list)
    # filters
    proj_min: float = 0.0
    # randomness (CBC)
    randomness_pct: float = 0.0
    # solver params (CP-SAT)
    cp_sat_params: dict[str, Any] = field(default_factory=dict)
    # ownership penalty
    ownership_penalty: OwnershipPenalty | None = None
    # DK strictness toggle in legacy code
    require_dk_ids: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.ownership_penalty is not None:
            d["ownership_penalty"] = asdict(self.ownership_penalty)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Constraints:
        if not d:
            return cls()
        d2 = dict(d)
        if "ownership_penalty" in d2 and d2["ownership_penalty"] is not None:
            d2["ownership_penalty"] = OwnershipPenalty.from_dict(
                d2.get("ownership_penalty")
            )
        return cls(**{k: v for k, v in d2.items() if k in cls().__annotations__})


@dataclass
class Player:
    player_id: str
    name: str
    pos: str
    team: str
    salary: int
    proj: float
    dk_id: str | None = None
    own_proj: float | None = None
    minutes: float | None = None
    stddev: float | None = None


@dataclass
class Lineup:
    lineup_id: int
    total_proj: float
    total_salary: int
    players: list[Player]
