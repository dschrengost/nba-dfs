"""Types and models for lineup validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum



class InvalidReason(Enum):
    """Enumerated error codes for lineup validation failures."""
    
    ROSTER_SIZE_MISMATCH = "roster_size_mismatch"
    SLOT_ELIGIBILITY_FAIL = "slot_eligibility_fail"
    SALARY_CAP_EXCEEDED = "salary_cap_exceeded"
    TEAM_LIMIT_EXCEEDED = "team_limit_exceeded"
    DUPLICATE_PLAYER = "duplicate_player"
    MISSING_PLAYER = "missing_player"
    INACTIVE_PLAYER = "inactive_player"
    INJURY_STATUS_BLOCKED = "injury_status_blocked"


@dataclass
class Rules:
    """Configuration for lineup validation rules."""
    
    # DK roster template - exactly 8 slots
    roster_slots: list[str] = None  # type: ignore[assignment]
    
    # Salary constraints
    salary_cap: int = 50000
    min_salary: int | None = None
    
    # Team constraints  
    max_per_team: int = 4
    
    # Player eligibility checks
    check_active_status: bool = True
    check_injury_status: bool = True
    blocked_injury_statuses: list[str] = None  # type: ignore[assignment]
    
    def __post_init__(self) -> None:
        if self.roster_slots is None:
            self.roster_slots = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
        if self.blocked_injury_statuses is None:
            self.blocked_injury_statuses = ["OUT", "Ineligible"]


@dataclass
class ValidationResult:
    """Result of lineup validation with detailed diagnostics."""
    
    valid: bool
    reasons: list[InvalidReason] = None  # type: ignore[assignment]
    slots: list[str] = None  # type: ignore[assignment]
    salary_total: int | None = None
    teams: dict[str, int] | None = None
    
    def __post_init__(self) -> None:
        if self.reasons is None:
            self.reasons = []
        if self.slots is None:
            self.slots = []


# DK position eligibility mapping: slot -> eligible positions
DK_POSITION_ELIGIBILITY: dict[str, list[str]] = {
    "PG": ["PG"],
    "SG": ["SG"], 
    "SF": ["SF"],
    "PF": ["PF"],
    "C": ["C"],
    "G": ["PG", "SG"],
    "F": ["SF", "PF"],
    "UTIL": ["PG", "SG", "SF", "PF", "C"],
}

# Default DK slot order
DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]