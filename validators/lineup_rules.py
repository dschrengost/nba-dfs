from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

DK_SLOTS_ORDER = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]

# mapping of slot -> eligible positions
POSITION_ELIGIBILITY: dict[str, set[str]] = {
    "PG": {"PG"},
    "SG": {"SG"},
    "SF": {"SF"},
    "PF": {"PF"},
    "C": {"C"},
    "G": {"PG", "SG"},
    "F": {"SF", "PF"},
    "UTIL": {"PG", "SG", "SF", "PF", "C"},
}


@dataclass
class LineupValidator:
    """Simple DK NBA lineup validator."""

    salary_cap: int = 50000
    max_per_team: int = 4

    def validate(
        self,
        lineup: Sequence[tuple[str, str]],
        player_pool: pd.DataFrame,
    ) -> bool:
        """Return True if lineup is valid under salary and eligibility rules."""
        if len(lineup) != 8:
            return False
        slots = [s for s, _ in lineup]
        if sorted(slots) != sorted(DK_SLOTS_ORDER):
            return False
        player_ids = [pid for _, pid in lineup]
        if len(set(player_ids)) != 8:
            return False
        try:
            sub = player_pool.set_index("player_id").loc[player_ids]
        except KeyError:
            return False
        # salary cap
        if int(sub["salary"].sum()) > self.salary_cap:
            return False
        # max per team
        team_counts = sub["team"].value_counts()
        if (team_counts > self.max_per_team).any():
            return False
        # slot eligibility
        for slot, pid in lineup:
            positions = str(sub.loc[pid, "positions"]).split("/")
            if not (POSITION_ELIGIBILITY.get(slot, set()) & set(positions)):
                return False
        return True
