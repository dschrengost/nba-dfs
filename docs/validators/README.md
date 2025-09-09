# DraftKings Lineup Validators

This module provides shared lineup validation functionality for NBA DFS lineups across all stages of the pipeline (optimizer, variant builder, field sampler).

## Overview

The shared validator eliminates code duplication and creates a single source of truth for DraftKings lineup validation rules. All validation logic is now centralized in the `validators` module.

## Quick Start

```python
from validators import validate_lineup, Rules

# Basic validation
player_pool = {
    "p1": {"salary": 10000, "positions": ["PG"], "team": "LAL", "is_active": True, "inj_status": ""},
    "p2": {"salary": 8000, "positions": ["SG"], "team": "GSW", "is_active": True, "inj_status": ""},
    # ... more players
}

lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]
rules = Rules()

result = validate_lineup(lineup, player_pool, rules)
if result.valid:
    print(f"Valid lineup with salary ${result.salary_total}")
else:
    print(f"Invalid lineup: {[r.value for r in result.reasons]}")
```

## API Reference

### Core Function

#### `validate_lineup(dk_player_ids, player_pool, rules) -> ValidationResult`

Validates a DraftKings lineup according to all specified rules.

**Parameters:**
- `dk_player_ids: List[str]` - List of 8 DraftKings player IDs
- `player_pool: Dict[str, Dict]` - Player data keyed by dk_player_id
- `rules: Rules` - Validation rules configuration

**Returns:**
- `ValidationResult` - Validation result with detailed diagnostics

### Data Models

#### `Rules`

Configuration for lineup validation rules.

```python
@dataclass
class Rules:
    roster_slots: List[str] = None  # Default: ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]
    salary_cap: int = 50000
    min_salary: Optional[int] = None
    max_per_team: int = 4
    check_active_status: bool = True
    check_injury_status: bool = True
    blocked_injury_statuses: List[str] = None  # Default: ["OUT", "Ineligible"]
```

#### `ValidationResult`

Result of lineup validation with detailed diagnostics.

```python
class ValidationResult(BaseModel):
    valid: bool
    reasons: List[InvalidReason] = []
    slots: List[str] = []  # Resolved slot assignments
    salary_total: Optional[int] = None
    teams: Optional[Dict[str, int]] = None  # Team -> player count
```

#### `InvalidReason`

Enumerated error codes for validation failures.

```python
class InvalidReason(Enum):
    ROSTER_SIZE_MISMATCH = "roster_size_mismatch"
    SLOT_ELIGIBILITY_FAIL = "slot_eligibility_fail"
    SALARY_CAP_EXCEEDED = "salary_cap_exceeded"
    TEAM_LIMIT_EXCEEDED = "team_limit_exceeded"
    DUPLICATE_PLAYER = "duplicate_player"
    MISSING_PLAYER = "missing_player"
    INACTIVE_PLAYER = "inactive_player"
    INJURY_STATUS_BLOCKED = "injury_status_blocked"
```

### Player Pool Format

Each player in the player_pool must have:

```python
{
    "salary": int,                    # Player salary
    "positions": List[str],           # Eligible positions (e.g., ["PG"], ["SF", "PF"])
    "team": str,                      # Team abbreviation
    "is_active": bool,                # Whether player is active (optional)
    "inj_status": str,                # Injury status (optional)
}
```

## DraftKings Position Rules

### Roster Template

A valid DK NBA lineup must have exactly 8 slots:
- **PG** (Point Guard)
- **SG** (Shooting Guard)
- **SF** (Small Forward)
- **PF** (Power Forward)
- **C** (Center)
- **G** (Guard - PG or SG eligible)
- **F** (Forward - SF or PF eligible)
- **UTIL** (Utility - any position eligible)

### Position Eligibility

Each slot can be filled by specific positions:

```python
DK_POSITION_ELIGIBILITY = {
    "PG": ["PG"],
    "SG": ["SG"],
    "SF": ["SF"],
    "PF": ["PF"],
    "C": ["C"],
    "G": ["PG", "SG"],
    "F": ["SF", "PF"],
    "UTIL": ["PG", "SG", "SF", "PF", "C"],
}
```

Multi-position players (e.g., "PG/SG") can fill any slot their positions are eligible for.

## Validation Rules

### 1. Roster Size
- Must have exactly 8 players
- Must fill exactly 8 DK slots

### 2. Player Eligibility
- All player IDs must exist in the player pool
- No duplicate players allowed
- Players must be able to fill DK roster slots based on positions

### 3. Salary Constraints
- Total salary ≤ `salary_cap` (default: $50,000)
- Optional minimum salary constraint

### 4. Team Limits
- Maximum `max_per_team` players from any single team (default: 4)

### 5. Active Status (optional)
- Players with `is_active: False` are rejected when `check_active_status: True`

### 6. Injury Status (optional)
- Players with injury status in `blocked_injury_statuses` are rejected when `check_injury_status: True`
- Default blocked statuses: ["OUT", "Ineligible"]

## Slot Assignment Algorithm

The validator uses a backtracking algorithm to assign players to slots:

1. Determine eligible slots for each player based on their positions
2. Sort players by constraint (fewest eligible slots first)
3. Use backtracking to find a valid assignment
4. Ensure all 8 slots are filled with unique players

## Integration Examples

### Optimizer Adapter

```python
from validators import Rules, validate_lineup

# Build player pool from projections DataFrame
player_pool = _build_player_pool(projections_df)
rules = Rules()

for lineup_data in lineups:
    players = lineup_data["players"]
    try:
        result = validate_lineup(players, player_pool, rules)
        if not result.valid:
            raise ValueError(f"Invalid lineup: {[r.value for r in result.reasons]}")
    except ValueError as e:
        # Handle validation error
        pass
```

### Variant Builder

```python
from validators import Rules, validate_lineup

# Convert Player objects to dict format
player_pool = {
    pid: {
        "salary": player.salary,
        "positions": player.positions,
        "team": player.team,
        "is_active": True,
        "inj_status": "",
    }
    for pid, player in pool.items()
}

rules = Rules(check_active_status=False, check_injury_status=False)
result = validate_lineup(lineup, player_pool, rules)
```

### Field Sampler

```python
from validators import Rules, validate_lineup

# Use relaxed rules for field sampler (minimal player data)
rules = Rules(
    salary_cap=999999,
    max_per_team=8,
    check_active_status=False,
    check_injury_status=False,
)

# Minimal player pool for structural validation only
player_pool = {
    pid: {
        "salary": 0,
        "positions": ["UTIL"],
        "team": "UNK",
        "is_active": True,
        "inj_status": "",
    }
    for pid in players
}

result = validate_lineup(players, player_pool, rules)
```

## Validation Metrics

Each stage that uses the validator outputs `validation_metrics.json` with:

```json
{
  "total_lineups": 100,
  "valid_lineups": 95,
  "invalid_lineups": 5,
  "reasons_count": {
    "Invalid lineup: salary_cap_exceeded": 3,
    "Invalid lineup: slot_eligibility_fail": 2
  }
}
```

## Testing

Run the validator tests:

```bash
pytest tests/test_lineup_rules.py -v
```

The test suite covers:
- Valid lineup acceptance
- All validation rule failures
- Multiple error scenarios
- Rules configuration options
- ValidationResult structure

## Migration Guide

### From Old LineupValidator

**Before:**
```python
from validators.lineup_rules import LineupValidator

validator = LineupValidator(salary_cap=45000, max_per_team=3)
lineup_tuples = [("PG", "p1"), ("SG", "p2"), ...]
is_valid = validator.validate(lineup_tuples, pool_df)
```

**After:**
```python
from validators import validate_lineup, Rules

rules = Rules(salary_cap=45000, max_per_team=3)
player_ids = ["p1", "p2", ...]
result = validate_lineup(player_ids, player_pool, rules)
is_valid = result.valid
```

### Building Player Pool from DataFrame

```python
def build_player_pool(df: pd.DataFrame) -> dict[str, dict]:
    player_pool = {}
    for _, row in df.iterrows():
        player_id = str(row["player_id"])
        positions = str(row.get("positions", "")).split("/")
        player_pool[player_id] = {
            "salary": int(row.get("salary", 0)),
            "positions": [p.strip() for p in positions if p.strip()],
            "team": str(row.get("team", "")),
            "is_active": row.get("is_active", True),
            "inj_status": row.get("inj_status", ""),
        }
    return player_pool
```

## Performance

The validator is optimized for performance:
- O(n) time complexity for most validations
- Efficient backtracking slot assignment
- Minimal memory overhead
- Pure functions with no I/O dependencies

## Error Handling

The validator never raises exceptions. All validation failures are returned in the `ValidationResult.reasons` list. This allows callers to decide how to handle specific validation failures.

For compatibility with existing code that expects exceptions, use the helper functions:

```python
from validators.lineup_rules import _validate_lineup_with_shared_validator

# Raises ValueError on validation failure
try:
    result = _validate_lineup_with_shared_validator(players, player_pool, rules)
except ValueError as e:
    print(f"Validation failed: {e}")
```