from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

from ..core.rules import F, PlayerState, RuleEngine
from .base import PlayerAgent


class RLModelAgent(PlayerAgent):
    def __init__(
        self,
        name: str,
        model_path: str,
        deterministic: bool = False,
    ):
        super().__init__(name)
        self.model_path = Path(model_path)
        self.deterministic = deterministic
        self._last_actions: Dict[int, str] = {}

        try:
            from sb3_contrib import MaskablePPO
        except ImportError as exc:
            raise RuntimeError(
                "RLModelAgent requires sb3-contrib in the active environment."
            ) from exc

        if not self.model_path.exists():
            raise FileNotFoundError(f"RL model file not found: {self.model_path}")

        self._model = MaskablePPO.load(str(self.model_path))

        from ..rl.config import OBS_DIM

        expected_obs_dim = int(self._model.observation_space.shape[0])
        if expected_obs_dim != OBS_DIM:
            raise RuntimeError(
                "RL checkpoint obs dim does not match current backend code: "
                f"checkpoint={expected_obs_dim}, current={OBS_DIM}"
            )

    def get_action(
        self,
        engine: RuleEngine,
        player_state: PlayerState,
        enemies: Sequence[PlayerState],
        is_first_round: bool,
    ) -> str:
        if is_first_round:
            return "蓄"

        from ..rl.config import ACTION_TO_IDX, ALL_ACTION_NAMES
        from ..rl.obs import encode_obs, get_action_mask

        enemy = enemies[0] if enemies else player_state
        agent_token = 0.0 if player_state.player_id % 2 == 1 else 1.0
        opp_token = 0.0 if enemy.player_id % 2 == 1 else 1.0
        agent_prev_action = self._last_actions.get(player_state.player_id, "蓄")
        opp_prev_action = self._last_actions.get(enemy.player_id, "蓄")
        context = {
            "agent_score_norm": 0.0,
            "opp_score_norm": 0.0,
            "rounds_completed_norm": 0.0,
            "equip_remaining_norm": 1.0,
            "passive_counter_norm": 0.0,
            "no_progress_counter_norm": 0.0,
            "mirror_counter_norm": 0.0,
            "agent_policy_token": agent_token,
            "opp_policy_token": opp_token,
            "agent_prev_action_idx": ACTION_TO_IDX.get(
                agent_prev_action, ACTION_TO_IDX["蓄"]
            ),
            "opp_prev_action_idx": ACTION_TO_IDX.get(
                opp_prev_action, ACTION_TO_IDX["蓄"]
            ),
        }
        obs = encode_obs(player_state, enemy, context)
        action_mask = get_action_mask(engine, player_state)
        action_idx, _ = self._model.predict(
            obs,
            action_masks=action_mask,
            deterministic=self.deterministic,
        )
        action_name = ALL_ACTION_NAMES[int(action_idx)]

        if action_name.startswith("超率:"):
            equip_name = action_name.split(":", 1)[1]
            if equip_name in engine.super_rate_candidates(player_state) and player_state.energy >= F(3):
                return action_name
            return "蓄"

        available_skills = engine.available_skills(player_state)
        if action_name not in available_skills:
            return "蓄"

        skill = available_skills[action_name]
        if skill.alt_cost and any(
            player_state.counters.get(k, 0) >= v for k, v in skill.alt_cost.items()
        ):
            return action_name
        if player_state.energy >= skill.energy_cost:
            return action_name
        return "蓄"

    def on_round_resolved(self, actions: Dict[int, str]) -> None:
        self._last_actions = dict(actions)

