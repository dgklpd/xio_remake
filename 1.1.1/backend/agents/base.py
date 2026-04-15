from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Sequence

from ..core.rules import PlayerState, RuleEngine


class PlayerAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_action(
        self,
        engine: RuleEngine,
        player_state: PlayerState,
        enemies: Sequence[PlayerState],
        is_first_round: bool,
    ) -> str:
        """Return the action name for the current round."""

    def on_round_resolved(self, actions: Dict[int, str]) -> None:
        """Hook for agents that need previous-round context."""
        return

