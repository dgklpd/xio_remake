from __future__ import annotations

import time
from typing import Dict, List

from ..agents.base import PlayerAgent
from .rules import RuleEngine, create_players


class GameSession:
    """CLI match loop built on top of the core rule engine."""

    def __init__(
        self,
        agents: List[PlayerAgent],
        *,
        max_turns_per_small_round: int | None = 20,
    ):
        self.engine = RuleEngine()
        self.agents: Dict[int, PlayerAgent] = {}
        self.players = create_players(len(agents))
        for player, agent in zip(self.players, agents):
            self.agents[player.player_id] = agent
        self.taken_equipments: set[str] = set()
        self.max_turns_per_small_round = max_turns_per_small_round

    def play_medium_round(self) -> int:
        for player in self.players:
            player.small_round_reset()

        self.engine.apply_welfare_if_needed(self.players)

        print("\n============================================================")
        print("                 New medium round started")
        print("============================================================\n")

        round_num = 1
        while True:
            print(f"\n--- Round {round_num} ---")
            is_first_round = round_num == 1

            declared_actions: dict[int, str] = {}
            for player in self.players:
                if not player.alive:
                    continue
                agent = self.agents[player.player_id]
                enemies = [p for p in self.players if p.player_id != player.player_id]
                action = agent.get_action(self.engine, player, enemies, is_first_round)
                declared_actions[player.player_id] = action

            result = self.engine.resolve_round(
                self.players,
                declared_actions,
                first_round_of_small_game=is_first_round,
            )

            for agent in self.agents.values():
                agent.on_round_resolved(result.actions)

            print("\n>> Resolution log")
            for player_id, action in result.actions.items():
                print(f"  [{self.agents[player_id].name}] played: {action}")
            for log in result.logs:
                print(f"  [system] {log}")

            if (
                self.max_turns_per_small_round is not None
                and round_num >= self.max_turns_per_small_round
            ):
                print(
                    f"\n[system] reached the per-round limit "
                    f"({self.max_turns_per_small_round}), this medium round is void."
                )
                return -1

            if result.draw_restart:
                print("\n[system] draw restart, resetting the small round.")
                for player in self.players:
                    player.small_round_reset()
                round_num = 1
                continue

            if result.dead_players:
                survivors = [
                    player
                    for player in self.players
                    if player.player_id not in result.dead_players
                ]
                if not survivors:
                    print("\n[system] unexpected state: no survivors.")
                    return -1

                winner = survivors[0]
                winner_agent = self.agents[winner.player_id]
                print(f"\nWinner: {winner_agent.name}")

                new_equip = self.engine.grant_next_equipment(
                    winner, self.taken_equipments
                )
                if new_equip:
                    self.taken_equipments.add(new_equip)
                    print(f"{winner_agent.name} gained equipment: {new_equip}")
                return winner.player_id

            round_num += 1
            time.sleep(1)

    def start_game_loop(self) -> None:
        print("Welcome to the Xio CLI arena.")
        scores = {player_id: 0 for player_id in self.agents}

        try:
            while True:
                winner_id = self.play_medium_round()
                if winner_id != -1:
                    scores[winner_id] += 1

                print("\nCurrent score:")
                for player_id, score in scores.items():
                    print(f"  {self.agents[player_id].name}: {score}")

                print("\nPreparing next medium round...")
                time.sleep(3)
        except KeyboardInterrupt:
            print("\nGame ended by user.")
            print("================ Final Score ================")
            for player_id, score in scores.items():
                print(f"  {self.agents[player_id].name}: {score}")
            print("============================================")
