from __future__ import annotations

import random
import time
from typing import Sequence

from ..core.rules import F, PlayerState, RuleEngine
from .base import PlayerAgent


class SimpleAIAgent(PlayerAgent):
    def __init__(self, name: str, think_time: float = 0.0):
        super().__init__(name)
        self.think_time = max(0.0, think_time)

    def _pause(self, seconds: float) -> None:
        if self.think_time > 0:
            time.sleep(seconds * self.think_time)

    def get_action(
        self,
        engine: RuleEngine,
        player_state: PlayerState,
        enemies: Sequence[PlayerState],
        is_first_round: bool,
    ) -> str:
        if is_first_round:
            return "蓄"

        available_skills = engine.available_skills(player_state)
        super_rate_list = engine.super_rate_candidates(player_state)
        max_enemy_energy = max((e.energy for e in enemies if e.alive), default=F(0))

        if super_rate_list and player_state.energy >= F(3):
            if max_enemy_energy < F(1) or player_state.energy >= F(6):
                equipment_to_upgrade = random.choice(super_rate_list)
                self._pause(1.0)
                return f"超率:{equipment_to_upgrade}"

        attacks = [
            s
            for s in available_skills.values()
            if s.category == "attack" and player_state.energy >= s.energy_cost
        ]
        defenses = [
            s
            for s in available_skills.values()
            if s.category == "defense" and player_state.energy >= s.energy_cost
        ]

        if max_enemy_energy == F(0):
            for attack in attacks:
                if attack.attack >= F(1) and attack.attack > F(1) and random.random() < 0.6:
                    self._pause(0.8)
                    return attack.name

        if max_enemy_energy >= F(3):
            strong_defs = [
                s
                for s in defenses
                if "mian_yi" in s.tags or s.name in ["超防", "大免", "挪移", "卡兹光"]
            ]
            if strong_defs and random.random() < 0.8:
                return random.choice(strong_defs).name

        candidates = ["蓄"]
        for defense in defenses:
            if defense.defense >= F("2.5"):
                candidates.append(defense.name)
        if player_state.energy >= F(1) and "波波" in available_skills:
            candidates.append("波波")
        if player_state.energy >= F("1/3") and "雷八" in available_skills:
            candidates.append("雷八")

        chosen = random.choice(candidates)
        if chosen not in available_skills:
            return "蓄"
        if player_state.energy < available_skills[chosen].energy_cost:
            return "蓄"
        self._pause(random.uniform(0.3, 1.2))
        return chosen


class RandomLegalAgent(PlayerAgent):
    def get_action(
        self,
        engine: RuleEngine,
        player_state: PlayerState,
        enemies: Sequence[PlayerState],
        is_first_round: bool,
    ) -> str:
        if is_first_round:
            return "蓄"

        available_skills = engine.available_skills(player_state)
        candidates: list[str] = []
        for action_name, skill in available_skills.items():
            if skill.alt_cost and any(
                player_state.counters.get(counter_name, 0) >= need
                for counter_name, need in skill.alt_cost.items()
            ):
                candidates.append(action_name)
                continue
            if player_state.energy >= skill.energy_cost:
                candidates.append(action_name)

        if player_state.energy >= F(3):
            candidates.extend(
                f"超率:{equip_name}"
                for equip_name in engine.super_rate_candidates(player_state)
            )

        if not candidates:
            return "蓄"
        return random.choice(candidates)

