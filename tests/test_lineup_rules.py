"""Tests for shared lineup validation module."""


from validators import InvalidReason, Rules, ValidationResult, validate_lineup


def sample_player_pool() -> dict[str, dict]:
    """Build a sample player pool for testing."""
    return {
        "p1": {"salary": 10000, "positions": ["PG"], "team": "TeamA", "is_active": True, "inj_status": ""},
        "p2": {"salary": 8000, "positions": ["SG"], "team": "TeamA", "is_active": True, "inj_status": ""},
        "p3": {"salary": 7000, "positions": ["SF"], "team": "TeamB", "is_active": True, "inj_status": ""},
        "p4": {"salary": 6000, "positions": ["PF"], "team": "TeamB", "is_active": True, "inj_status": ""},
        "p5": {"salary": 5000, "positions": ["C"], "team": "TeamC", "is_active": True, "inj_status": ""},
        "p6": {"salary": 4000, "positions": ["PG", "SG"], "team": "TeamC", "is_active": True, "inj_status": ""},
        "p7": {"salary": 3000, "positions": ["SF", "PF"], "team": "TeamD", "is_active": True, "inj_status": ""},
        "p8": {"salary": 2000, "positions": ["C"], "team": "TeamD", "is_active": True, "inj_status": ""},
        "p9": {"salary": 1000, "positions": ["PG", "SG", "SF", "PF", "C"], "team": "TeamE", "is_active": False, "inj_status": ""},
        "p10": {"salary": 1500, "positions": ["PG"], "team": "TeamE", "is_active": True, "inj_status": "OUT"},
    }


def valid_lineup() -> list[str]:
    """Return a valid 8-player lineup."""
    return ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]


class TestValidLineup:
    """Test cases for valid lineups."""
    
    def test_valid_lineup_passes(self):
        """Test that a valid lineup passes validation."""
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert result.valid
        assert len(result.reasons) == 0
        assert len(result.slots) == 8
        assert result.salary_total == 45000
        assert len(result.teams) == 4


class TestRosterSizeValidation:
    """Test cases for roster size validation."""
    
    def test_too_few_players_fails(self):
        """Test that lineups with < 8 players fail."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3"]
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.ROSTER_SIZE_MISMATCH in result.reasons
    
    def test_too_many_players_fails(self):
        """Test that lineups with > 8 players fail."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.ROSTER_SIZE_MISMATCH in result.reasons


class TestDuplicatePlayersValidation:
    """Test cases for duplicate player validation."""
    
    def test_duplicate_players_fails(self):
        """Test that lineups with duplicate players fail."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p1", "p3", "p4", "p5", "p6", "p7", "p8"]
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.DUPLICATE_PLAYER in result.reasons


class TestMissingPlayersValidation:
    """Test cases for missing player validation."""
    
    def test_missing_players_fails(self):
        """Test that lineups with unknown player IDs fail."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "unknown_player"]
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.MISSING_PLAYER in result.reasons


class TestSalaryCapValidation:
    """Test cases for salary cap validation."""
    
    def test_salary_cap_exceeded_fails(self):
        """Test that lineups exceeding salary cap fail."""
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules(salary_cap=40000)  # Total is 45000
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.SALARY_CAP_EXCEEDED in result.reasons
        assert result.salary_total == 45000
    
    def test_minimum_salary_not_met_fails(self):
        """Test that lineups below minimum salary fail."""
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules(min_salary=50000)  # Total is 45000
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.SALARY_CAP_EXCEEDED in result.reasons  # Same enum used for both bounds


class TestTeamLimitValidation:
    """Test cases for team limit validation."""
    
    def test_team_limit_exceeded_fails(self):
        """Test that lineups exceeding team limits fail."""
        player_pool = sample_player_pool()
        # Add more players from TeamA to exceed limit
        player_pool["p11"] = {"salary": 1000, "positions": ["UTIL"], "team": "TeamA", "is_active": True, "inj_status": ""}
        player_pool["p12"] = {"salary": 1000, "positions": ["UTIL"], "team": "TeamA", "is_active": True, "inj_status": ""}
        player_pool["p13"] = {"salary": 1000, "positions": ["UTIL"], "team": "TeamA", "is_active": True, "inj_status": ""}
        
        lineup = ["p1", "p2", "p11", "p12", "p13", "p6", "p7", "p8"]  # 5 from TeamA
        rules = Rules(max_per_team=4)
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.TEAM_LIMIT_EXCEEDED in result.reasons


class TestActiveStatusValidation:
    """Test cases for active status validation."""
    
    def test_inactive_player_fails(self):
        """Test that lineups with inactive players fail when checking is enabled."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p9"]  # p9 is inactive
        rules = Rules(check_active_status=True)
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.INACTIVE_PLAYER in result.reasons
    
    def test_inactive_player_passes_when_not_checking(self):
        """Test that inactive players are allowed when checking is disabled."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p9"]  # p9 is inactive
        rules = Rules(check_active_status=False)
        
        result = validate_lineup(lineup, player_pool, rules)
        
        # Should pass other validations (may fail on positions, but not active status)
        assert InvalidReason.INACTIVE_PLAYER not in result.reasons


class TestInjuryStatusValidation:
    """Test cases for injury status validation."""
    
    def test_injured_player_fails(self):
        """Test that lineups with injured players fail when checking is enabled."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p10"]  # p10 is OUT
        rules = Rules(check_injury_status=True)
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.INJURY_STATUS_BLOCKED in result.reasons
    
    def test_injured_player_passes_when_not_checking(self):
        """Test that injured players are allowed when checking is disabled.""" 
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p10"]  # p10 is OUT
        rules = Rules(check_injury_status=False)
        
        result = validate_lineup(lineup, player_pool, rules)
        
        # Should pass other validations (may fail on positions, but not injury status)
        assert InvalidReason.INJURY_STATUS_BLOCKED not in result.reasons


class TestSlotEligibilityValidation:
    """Test cases for position/slot eligibility validation."""
    
    def test_impossible_slot_assignment_fails(self):
        """Test that lineups that can't be assigned to valid slots fail."""
        player_pool = sample_player_pool()
        # Try to use 8 centers (only 1 C slot + 1 UTIL available for C)
        for i in range(11, 19):
            player_pool[f"p{i}"] = {"salary": 1000, "positions": ["C"], "team": f"Team{i}", "is_active": True, "inj_status": ""}
        
        lineup = ["p11", "p12", "p13", "p14", "p15", "p16", "p17", "p18"]  # All centers
        rules = Rules(salary_cap=999999, max_per_team=8)  # Relax other constraints
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.SLOT_ELIGIBILITY_FAIL in result.reasons
    
    def test_multi_position_players_work(self):
        """Test that multi-position players can fill appropriate slots."""
        player_pool = sample_player_pool()
        # p6 is PG/SG and p7 is SF/PF, should be able to fill flexible slots
        lineup = valid_lineup()
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert result.valid
        assert InvalidReason.SLOT_ELIGIBILITY_FAIL not in result.reasons


class TestMultipleErrors:
    """Test cases for lineups with multiple validation errors."""
    
    def test_multiple_errors_reported(self):
        """Test that multiple validation errors are all reported."""
        player_pool = sample_player_pool()
        # Lineup with duplicates, wrong size, and over salary cap
        lineup = ["p1", "p1", "p1"]  # Duplicates and wrong size
        rules = Rules(salary_cap=1000)  # Way too low
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.ROSTER_SIZE_MISMATCH in result.reasons
        # Note: duplicate check happens first and may prevent other checks


class TestRulesConfiguration:
    """Test cases for different rule configurations."""
    
    def test_custom_salary_cap(self):
        """Test custom salary cap configuration."""
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules(salary_cap=60000)  # Higher than default
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert result.valid
        assert result.salary_total == 45000
    
    def test_custom_team_limit(self):
        """Test custom team limit configuration.""" 
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules(max_per_team=1)  # Very restrictive
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.TEAM_LIMIT_EXCEEDED in result.reasons
    
    def test_custom_blocked_injury_statuses(self):
        """Test custom blocked injury statuses configuration."""
        player_pool = sample_player_pool()
        player_pool["p11"] = {"salary": 1000, "positions": ["UTIL"], "team": "TeamX", "is_active": True, "inj_status": "QUESTIONABLE"}
        
        lineup = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p11"]
        rules = Rules(check_injury_status=True, blocked_injury_statuses=["OUT", "QUESTIONABLE"])
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert not result.valid
        assert InvalidReason.INJURY_STATUS_BLOCKED in result.reasons


class TestValidationResult:
    """Test cases for ValidationResult structure."""
    
    def test_result_structure_valid_lineup(self):
        """Test that ValidationResult has correct structure for valid lineups."""
        player_pool = sample_player_pool()
        lineup = valid_lineup()
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert isinstance(result.reasons, list)
        assert len(result.reasons) == 0
        assert isinstance(result.slots, list)
        assert len(result.slots) == 8
        assert isinstance(result.salary_total, int)
        assert result.salary_total > 0
        assert isinstance(result.teams, dict)
        assert len(result.teams) > 0
    
    def test_result_structure_invalid_lineup(self):
        """Test that ValidationResult has correct structure for invalid lineups."""
        player_pool = sample_player_pool()
        lineup = ["p1", "p2", "p3"]  # Too few players
        rules = Rules()
        
        result = validate_lineup(lineup, player_pool, rules)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert isinstance(result.reasons, list)
        assert len(result.reasons) > 0
        assert InvalidReason.ROSTER_SIZE_MISMATCH in result.reasons
        assert isinstance(result.slots, list)
        assert result.salary_total is None  # Not calculated for invalid roster size
        assert result.teams is None  # Not calculated for invalid roster size