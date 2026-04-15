from __future__ import annotations

from typing import Dict, List, Sequence

from ..core.rules import F, PlayerState, RuleEngine, Skill, format_energy
from .base import PlayerAgent


class HumanCLIAgent(PlayerAgent):
    def get_action(
        self,
        engine: RuleEngine,
        player_state: PlayerState,
        enemies: Sequence[PlayerState],
        is_first_round: bool,
    ) -> str:
        if is_first_round:
            print(f"\n[{self.name}] first round is forced to charge.")
            return "蓄"

        available_skills = engine.available_skills(player_state)
        super_rate_list = engine.super_rate_candidates(player_state)

        while True:
            print(f"\n=== {self.name} turn ===")
            print(
                f"energy={format_energy(player_state.energy)} "
                f"statuses={sorted(player_state.statuses) if player_state.statuses else 'none'}"
            )

            if player_state.equipments:
                equip_strs = [
                    f"{name}(phase {state.phase})"
                    for name, state in player_state.equipments.items()
                ]
                print("equipment:", ", ".join(equip_strs))

            skills_by_category: Dict[str, List[Skill]] = {
                "attack": [],
                "defense": [],
                "special": [],
            }
            for skill in available_skills.values():
                category = (
                    skill.category
                    if skill.category in skills_by_category
                    else "special"
                )
                skills_by_category[category].append(skill)

            for category_name, skills in skills_by_category.items():
                if not skills:
                    continue
                rendered = " | ".join(
                    [
                        f"{s.name}(atk:{format_energy(s.attack)} def:{format_energy(s.defense)} cost:{format_energy(s.energy_cost)})"
                        for s in skills
                    ]
                )
                print(f"{category_name}: {rendered}")

            if super_rate_list and player_state.energy >= F(3):
                print(
                    "super rate:",
                    ", ".join([f"超率:{equip_name}" for equip_name in super_rate_list]),
                )

            action = input("action> ").strip()

            if action.startswith("超率:"):
                equip_name = action.split(":", 1)[1] if ":" in action else ""
                if equip_name in super_rate_list and player_state.energy >= F(3):
                    return action
                print("invalid super rate target")
                continue

            if action in available_skills:
                skill = available_skills[action]
                if skill.alt_cost and any(
                    player_state.counters.get(k, 0) >= v
                    for k, v in skill.alt_cost.items()
                ):
                    return action
                if player_state.energy >= skill.energy_cost:
                    return action
                print("not enough energy")
                continue

            print("invalid action")

