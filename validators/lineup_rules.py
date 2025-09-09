"""Core DraftKings lineup validation rules."""

from __future__ import annotations

from typing import Any

from .types import (
    DK_POSITION_ELIGIBILITY,
    InvalidReason,
    Rules,
    ValidationResult,
)


def validate_lineup(
    dk_player_ids: list[str],
    player_pool: dict[str, dict[str, Any]],
    rules: Rules,
) -> ValidationResult:
    """Validate a DraftKings lineup according to all rules.
    
    Pure function with no I/O dependencies.
    
    Args:
        dk_player_ids: List of player IDs in the lineup
        player_pool: Dict keyed by dk_player_id with player data:
            - salary: int
            - positions: list[str] (e.g., ["PG"], ["SF", "PF"])  
            - team: str
            - is_active: bool (optional)
            - inj_status: str (optional)
        rules: Rules configuration object
        
    Returns:
        ValidationResult with validation status and detailed diagnostics
    """
    reasons: list[InvalidReason] = []
    slots: list[str] = []
    salary_total: int | None = None
    teams: dict[str, int] | None = None
    
    # Check roster size
    if len(dk_player_ids) != len(rules.roster_slots):
        reasons.append(InvalidReason.ROSTER_SIZE_MISMATCH)
        return ValidationResult(
            valid=False, 
            reasons=reasons,
            slots=slots,
            salary_total=salary_total,
            teams=teams
        )
    
    # Check for duplicate players
    if len(set(dk_player_ids)) != len(dk_player_ids):
        reasons.append(InvalidReason.DUPLICATE_PLAYER)
    
    # Check all players exist in pool
    missing_players = [pid for pid in dk_player_ids if pid not in player_pool]
    if missing_players:
        reasons.append(InvalidReason.MISSING_PLAYER)
    
    # If we have missing players or duplicates, we can't continue with other validations
    if reasons:
        return ValidationResult(
            valid=False,
            reasons=reasons, 
            slots=slots,
            salary_total=salary_total,
            teams=teams
        )
    
    # Calculate salary total
    salary_total = sum(player_pool[pid].get("salary", 0) for pid in dk_player_ids)
    
    # Check salary cap
    if salary_total > rules.salary_cap:
        reasons.append(InvalidReason.SALARY_CAP_EXCEEDED)
    
    # Check minimum salary if specified
    if rules.min_salary is not None and salary_total < rules.min_salary:
        reasons.append(InvalidReason.SALARY_CAP_EXCEEDED)  # Same enum for both bounds
    
    # Count players per team
    teams = {}
    for pid in dk_player_ids:
        team = player_pool[pid].get("team", "")
        teams[team] = teams.get(team, 0) + 1
    
    # Check team limits
    for _team, count in teams.items():
        if count > rules.max_per_team:
            reasons.append(InvalidReason.TEAM_LIMIT_EXCEEDED)
            break
    
    # Check active status
    if rules.check_active_status:
        for pid in dk_player_ids:
            is_active = player_pool[pid].get("is_active")
            if is_active is not None and not is_active:
                reasons.append(InvalidReason.INACTIVE_PLAYER)
                break
    
    # Check injury status
    if rules.check_injury_status:
        for pid in dk_player_ids:
            inj_status = player_pool[pid].get("inj_status")
            if inj_status in rules.blocked_injury_statuses:
                reasons.append(InvalidReason.INJURY_STATUS_BLOCKED)
                break
    
    # Check slot eligibility - try to assign players to slots
    slot_assignment = _assign_slots_to_players(dk_player_ids, player_pool, rules)
    if slot_assignment is None:
        reasons.append(InvalidReason.SLOT_ELIGIBILITY_FAIL)
        slots = []
    else:
        slots = [slot for slot, _ in slot_assignment]
    
    valid = len(reasons) == 0
    
    return ValidationResult(
        valid=valid,
        reasons=reasons,
        slots=slots,
        salary_total=salary_total,
        teams=teams
    )


def _assign_slots_to_players(
    dk_player_ids: list[str],
    player_pool: dict[str, dict[str, Any]], 
    rules: Rules
) -> list[tuple[str, str]] | None:
    """Try to assign players to DK slots using backtracking.
    
    Returns:
        List of (slot, player_id) tuples if assignment is possible, None otherwise
    """
    # Get eligible slots for each player
    player_eligible_slots: dict[str, list[str]] = {}
    for pid in dk_player_ids:
        player_data = player_pool[pid]
        positions = player_data.get("positions", [])
        if not positions:
            return None
            
        eligible_slots: list[str] = []
        # For each slot, check if this player's positions can fill it
        for slot in rules.roster_slots:
            slot_eligible_positions = DK_POSITION_ELIGIBILITY.get(slot, [])
            # If any of the player's positions can fill this slot
            if any(pos in slot_eligible_positions for pos in positions):
                eligible_slots.append(slot)
        
        player_eligible_slots[pid] = eligible_slots
        if not eligible_slots:
            return None
    
    # Sort players by constraint (fewest eligible slots first)
    sorted_players = sorted(
        dk_player_ids, 
        key=lambda pid: len(player_eligible_slots[pid])
    )
    
    # Backtracking assignment
    assignment: list[tuple[str, str]] = []
    used_slots: set[str] = set()
    
    def backtrack(player_idx: int) -> bool:
        if player_idx == len(sorted_players):
            return True
        
        pid = sorted_players[player_idx]
        for slot in player_eligible_slots[pid]:
            if slot not in used_slots:
                used_slots.add(slot)
                assignment.append((slot, pid))
                
                if backtrack(player_idx + 1):
                    return True
                
                # Backtrack
                assignment.pop()
                used_slots.remove(slot)
        
        return False
    
    if backtrack(0):
        # Sort assignment by slot order for consistent output
        slot_order = {slot: i for i, slot in enumerate(rules.roster_slots)}
        assignment.sort(key=lambda x: slot_order.get(x[0], 999))
        return assignment
    
    return None


def validate_lineup_simple(
    dk_player_ids: list[str],
    player_pool: dict[str, dict[str, Any]],
    salary_cap: int = 50000,
    max_per_team: int = 4,
) -> bool:
    """Simple boolean validation for backward compatibility."""
    rules = Rules(salary_cap=salary_cap, max_per_team=max_per_team)
    result = validate_lineup(dk_player_ids, player_pool, rules)
    return result.valid