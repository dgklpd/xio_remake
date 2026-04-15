"""
model/env.py
═══════════════════════════════════════════════════════════════════
Gymnasium 环境包装器（单智能体视角的 1v1 对局）。

设计要点：
  - 学习智能体固定为 player_id=1（先手）
  - 对手由可插拔的 OpponentPolicy 驱动（随机/规则AI/历史模型）
  - Episode = 一个完整小局（从重置到一方死亡）
  - 第一回合（强制蓄）在 reset() 内自动结算，agent 从第二回合起决策
  - 实现 action_masks() 方法，满足 sb3-contrib MaskablePPO 的接口约定
  - 通过 set_opponent() 支持热更新对手，供自我博弈回调使用

v2 变更：
  - 修复平局处理：draw_restart 不再终止 episode，与实际游戏规则对齐
  - 增强奖励函数：新增蓄能激励、攻击激励、消极惩罚
  - 添加 per-episode 招式统计，通过 info 输出供日志收集

对手接口约定（OpponentPolicy）：
  predict(obs: np.ndarray, action_mask: np.ndarray) -> int
  on_episode_reset() -> None  （可选，用于每局换一个历史模型）
═══════════════════════════════════════════════════════════════════
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from ..core.rules import RuleEngine, PlayerState, SKILLS, create_players
from .config import (
    OBS_DIM,
    N_ACTIONS,
    ALL_ACTION_NAMES,
    ACTION_TO_IDX,
    REWARD_ROUND_WIN,
    REWARD_ROUND_LOSE,
    REWARD_MATCH_WIN,
    REWARD_MATCH_LOSE,
    REWARD_DRAW,
    REWARD_SMASH_ENEMY,
    REWARD_SMASH_SELF,
    REWARD_SUPER_RATE,
    REWARD_CHARGE_WHEN_SAFE,
    REWARD_KILL_ATTEMPT,
    REWARD_PASSIVE_PENALTY,
    REWARD_STALEMATE_PENALTY,
    REWARD_STALEMATE_ESCALATION,
    REWARD_MIRROR_STALEMATE,
    REWARD_TRUNCATION,
    PASSIVE_THRESHOLD,
    REWARD_STEP_COST,
    MAX_TURNS_PER_SMALL_ROUND,
    MATCH_ROUND_LIMIT,
    MAX_NO_PROGRESS_STREAK,
    MAX_MIRROR_STREAK,
)
from .obs import encode_obs, get_action_mask
from .config import EQUIPMENT_POOL


# ═════════════════════════════════════════════════════════════════════════════
#  对手策略基类 & 常见实现
# ═════════════════════════════════════════════════════════════════════════════


class OpponentPolicy:
    """对手策略的抽象接口，所有对手均实现此类。"""

    def predict(self, obs: np.ndarray, action_mask: np.ndarray) -> int:
        """根据观测和合法动作掩码，返回动作索引。"""
        raise NotImplementedError

    def on_episode_reset(self) -> None:
        """每局重置时被调用（可选，用于池化采样等需要刷新状态的场景）。"""
        pass

    def bind_env(
        self,
        engine: RuleEngine,
        players: Sequence[PlayerState],
        controlled_index: int = 1,
    ) -> None:
        """在环境 reset 时将底层规则上下文同步给对手。"""
        pass


class RandomOpponent(OpponentPolicy):
    """随机对手：从所有合法动作中均匀随机选择。用于热身训练和基准评估。"""

    def predict(self, obs: np.ndarray, action_mask: np.ndarray) -> int:
        valid = np.where(action_mask)[0]
        return int(np.random.choice(valid))


class ModelOpponent(OpponentPolicy):
    """
    加载好的 MaskablePPO 模型对手。
    适用于评估与固定对手对打的胜率。
    """

    def __init__(self, model: Any):
        self.model = model

    def predict(self, obs: np.ndarray, action_mask: np.ndarray) -> int:
        # MaskablePPO.predict 接受批次维度，因此 unsqueeze
        action, _ = self.model.predict(
            obs[np.newaxis],
            action_masks=action_mask[np.newaxis],
            deterministic=True,
        )
        return int(action[0])


class RuleBasedOpponent(OpponentPolicy):
    """
    规则驱动对手（对接 agent.py 中的 SimpleAIAgent），
    用于早期训练阶段给 RL 智能体提供比随机更高质量的对手。
    """

    def __init__(self):
        self._engine: Optional[RuleEngine] = None
        self._player: Optional[PlayerState] = None
        self._players: Sequence[PlayerState] = []
        self._ai = None

    def bind_env(
        self,
        engine: RuleEngine,
        players: Sequence[PlayerState],
        controlled_index: int = 1,
    ) -> None:
        self._engine = engine
        self._players = players
        self._player = (
            players[controlled_index] if len(players) > controlled_index else None
        )
        try:
            from ..agents.rule_agents import SimpleAIAgent

            self._ai = SimpleAIAgent("rule_ai")
        except Exception:
            self._ai = None

    def predict(self, obs: np.ndarray, action_mask: np.ndarray) -> int:
        """调用规则AI，将技能名转回动作索引。"""
        if (
            self._engine is not None
            and self._player is not None
            and self._ai is not None
        ):
            enemies = [p for p in self._players if p is not self._player]
            try:
                action_str = self._ai.get_action(
                    self._engine, self._player, enemies, is_first_round=False
                )
                idx = ACTION_TO_IDX.get(action_str)
                if idx is not None and action_mask[idx]:
                    return idx
            except Exception:
                pass
        # 降级到随机
        valid = np.where(action_mask)[0]
        return int(np.random.choice(valid))


# ═════════════════════════════════════════════════════════════════════════════
#  Gymnasium 环境
# ═════════════════════════════════════════════════════════════════════════════


class XiaoGameEnv(gym.Env):
    """
    拍手游戏的 Gymnasium 单智能体包装环境。

    Observation Space: Box(0, 1, shape=(OBS_DIM,), float32)
    Action Space:      Discrete(N_ACTIONS)
    Episode:           一个完整 小局（小局第一回合在 reset() 内自动结算）

    v2 变更：
      - 平局（draw_restart）不再终止 episode，与实际游戏规则对齐
      - 增加 per-episode 招式统计，通过 info 输出
      - 增强奖励塑形：蓄能激励、攻击激励、消极惩罚

    与 sb3-contrib MaskablePPO 集成：
      - 实现了 action_masks() 方法
      - VecEnv 会通过 env_method("action_masks") 调用
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        opponent: Optional[OpponentPolicy] = None,
        randomize_agent_side: bool = True,
    ):
        super().__init__()

        # 动作 / 观测空间定义
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(N_ACTIONS)

        # 规则引擎（每个 env 实例独立持有，保证并行安全）
        self.engine = RuleEngine()

        # 对手策略（可通过 set_opponent 热更新）
        self.opponent: OpponentPolicy = opponent or RandomOpponent()
        self.randomize_agent_side = randomize_agent_side

        # 游戏状态
        self._players: Optional[List[PlayerState]] = None
        self._turn_in_small_round: int = 0
        self._completed_rounds: int = 0
        self._match_scores: Dict[int, int] = {}
        self._taken_equipments: Set[str] = set()
        self._ep_reward: float = 0.0
        self._total_turns: int = 0
        self._match_round_limit: int = MATCH_ROUND_LIMIT
        self._policy_tokens: Dict[int, float] = {}
        self._last_actions: Dict[int, str] = {}
        self._agent_index: int = 0

        # v2: per-episode 招式统计
        self._agent_action_counts: Counter = Counter()
        self._opp_action_counts: Counter = Counter()
        self._passive_counter: int = 0  # 连续无攻击回合计数
        self._draw_count: int = 0  # 当前小局内平局重开次数
        self._no_progress_counter: int = 0  # 连续无进展回合计数
        self._mirror_counter: int = 0  # 连续镜像无进展回合计数

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def set_opponent(self, opponent: OpponentPolicy) -> None:
        """热更换对手策略（无需重置环境）。自我博弈回调通过此方法更新对手。"""
        self.opponent = opponent
        if self._players is not None:
            self.opponent.bind_env(self.engine, self._players, self._opp_index())

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)

        # 初始化玩家状态（player_id=1 ← 学习智能体，player_id=2 ← 对手）
        self._players = create_players(2)
        self._agent_index = np.random.randint(2) if self.randomize_agent_side else 0
        self._match_scores = {p.player_id: 0 for p in self._players}
        self._completed_rounds = 0
        self._taken_equipments = set()
        self._turn_in_small_round = 0
        self._ep_reward = 0.0
        self._total_turns = 0

        # 重置统计计数器
        self._agent_action_counts = Counter()
        self._opp_action_counts = Counter()
        self._passive_counter = 0
        self._draw_count = 0
        self._no_progress_counter = 0
        self._mirror_counter = 0
        self._last_actions = {}

        # 通知对手新局开始
        self.opponent.bind_env(self.engine, self._players, self._opp_index())
        self.opponent.on_episode_reset()
        self._assign_policy_tokens()

        # 启动首个小局
        self._prepare_small_round()

        return self._get_obs(), {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        assert self._players is not None, "请先调用 reset()"

        agent_player = self._agent_player()
        opp_player = self._opp_player()
        agent_id = agent_player.player_id
        opp_id = opp_player.player_id
        opp_energy_before = float(opp_player.energy)

        agent_action_str = self._safe_decode(action, agent_player)

        opp_obs = encode_obs(
            opp_player, agent_player, self._match_context(for_agent=False)
        )
        opp_mask = get_action_mask(self.engine, opp_player)
        opp_action_idx = self.opponent.predict(opp_obs, opp_mask)
        opp_action_str = self._safe_decode(opp_action_idx, opp_player)

        self._agent_action_counts[agent_action_str] += 1
        self._opp_action_counts[opp_action_str] += 1

        try:
            result = self.engine.resolve_round(
                self._players,
                {agent_id: agent_action_str, opp_id: opp_action_str},
            )
        except ValueError:
            result = self.engine.resolve_round(
                self._players,
                {agent_id: "蓄", opp_id: "蓄"},
            )

        self._turn_in_small_round += 1
        self._total_turns += 1

        round_outcome: Optional[str] = None
        match_finished = False
        match_result: Optional[str] = None
        termination_reason: Optional[str] = None

        if result.draw_restart:
            self._draw_count += 1
        elif agent_id in result.dead_players and opp_id in result.dead_players:
            self._draw_count += 1
        elif result.dead_players:
            if opp_id in result.dead_players:
                round_outcome = "win"
                winner_id = agent_id
            else:
                round_outcome = "loss"
                winner_id = opp_id
            self._match_scores[winner_id] += 1
            self._completed_rounds += 1
            if self._is_match_over():
                match_finished = True
                match_result = self._final_match_result()

        agent_smashed = result.smashed_this_round.get(agent_id, set())
        opp_smashed = result.smashed_this_round.get(opp_id, set())
        no_progress = (
            not result.dead_players
            and not agent_smashed
            and not opp_smashed
            and not agent_action_str.startswith("超率:")
            and not opp_action_str.startswith("超率:")
        )
        mirrored_stalemate = no_progress and agent_action_str == opp_action_str
        self._update_stalemate_counters(no_progress, mirrored_stalemate)

        reward = self._compute_reward(
            agent_id,
            agent_action_str,
            round_outcome,
            opp_energy_before,
            agent_smashed,
            opp_smashed,
            no_progress,
            mirrored_stalemate,
        )
        self._ep_reward += reward

        if result.draw_restart:
            self._prepare_small_round()
        elif agent_id in result.dead_players and opp_id in result.dead_players:
            self._prepare_small_round()
        elif result.dead_players:
            self._award_equipment(winner_id)
            if not match_finished:
                self._prepare_small_round()
        else:
            self._last_actions = {agent_id: agent_action_str, opp_id: opp_action_str}

        terminated = False
        truncated = False

        if match_finished:
            terminated = True
            if match_result == "win":
                reward += REWARD_MATCH_WIN
            elif match_result == "loss":
                reward += REWARD_MATCH_LOSE
            else:
                reward += REWARD_DRAW

        forced_stalemate = (
            self._no_progress_counter >= MAX_NO_PROGRESS_STREAK
            or self._mirror_counter >= MAX_MIRROR_STREAK
        )
        if forced_stalemate and not terminated:
            truncated = True
            terminated = True
            reward += REWARD_TRUNCATION
            if match_result is None:
                match_result = "truncated"
            termination_reason = "stale_loop"
        elif self._turn_in_small_round >= MAX_TURNS_PER_SMALL_ROUND:
            truncated = True
            terminated = True
            reward += REWARD_TRUNCATION
            if match_result is None:
                match_result = "truncated"
            termination_reason = "turn_limit"

        obs = self._get_obs()
        info: Dict[str, Any] = {
            "turn_in_round": self._turn_in_small_round,
            "dead_players": result.dead_players,
            "draw": result.draw_restart,
            "ep_reward": self._ep_reward,
            "match_scores": dict(self._match_scores),
            "completed_rounds": self._completed_rounds,
            "no_progress_streak": self._no_progress_counter,
            "mirror_streak": self._mirror_counter,
        }

        if match_result is not None:
            info["match_result"] = match_result
        if termination_reason is not None:
            info["termination_reason"] = termination_reason

        if terminated:
            if match_result is None:
                match_result = "truncated"
            info["episode_stats"] = {
                "agent_action_counts": dict(self._agent_action_counts),
                "opp_action_counts": dict(self._opp_action_counts),
                "result": match_result,
                "n_rounds": self._total_turns,
                "draw_count": self._draw_count,
            }

        return obs, reward, terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """
        供 sb3-contrib MaskablePPO 调用的合法动作掩码接口。
        VecEnv 会通过 env_method("action_masks") 批量收集。
        """
        if self._players is None:
            return np.ones(N_ACTIONS, dtype=bool)
        return get_action_mask(self.engine, self._agent_player())

    def render(self) -> None:
        if self._players is not None:
            p1, p2 = self._agent_player(), self._opp_player()
            print(
                f"小局回合 {self._turn_in_small_round} | "
                f"Agent 能量={float(p1.energy):.2f} | "
                f"Opp 能量={float(p2.energy):.2f}"
            )

    # ── 内部辅助 ─────────────────────────────────────────────────────────────

    def _prepare_small_round(self) -> None:
        if self._players is None:
            return
        for p in self._players:
            p.small_round_reset()
        self.engine.apply_welfare_if_needed(self._players)
        self._passive_counter = 0
        self._draw_count = 0
        self._no_progress_counter = 0
        self._mirror_counter = 0
        self._turn_in_small_round = 0
        self.engine.resolve_round(self._players, {}, first_round_of_small_game=True)
        self._turn_in_small_round = 1
        self._last_actions = {player.player_id: "蓄" for player in self._players}

    def _update_stalemate_counters(
        self,
        no_progress: bool,
        mirrored_stalemate: bool,
    ) -> None:
        if no_progress:
            self._no_progress_counter += 1
        else:
            self._no_progress_counter = 0

        if mirrored_stalemate:
            self._mirror_counter += 1
        else:
            self._mirror_counter = 0

    def _get_obs(self) -> np.ndarray:
        return encode_obs(
            self._agent_player(),
            self._opp_player(),
            self._match_context(for_agent=True),
        )

    def _assign_policy_tokens(self) -> None:
        if self._players is None or len(self._players) < 2:
            self._policy_tokens = {}
            return
        self._policy_tokens = {
            self._players[0].player_id: 0.0,
            self._players[1].player_id: 1.0,
        }

    def _safe_decode(self, action_idx: int, player: PlayerState) -> str:
        """
        将动作索引解码为技能名，并验证合法性。
        非法动作自动降级为 "蓄"（零能量消耗，永远安全）。
        """
        if not (0 <= action_idx < N_ACTIONS):
            return "蓄"

        name = ALL_ACTION_NAMES[action_idx]
        energy_f = float(player.energy)

        # 超率动作校验
        if name.startswith("超率:"):
            equip = name.split(":", 1)[1]
            if equip in self.engine.super_rate_candidates(player) and energy_f >= 3.0:
                return name
            return "蓄"

        # 普通技能校验
        available = self.engine.available_skills(player)
        if name not in available:
            return "蓄"

        skill = available[name]
        if skill.alt_cost:
            has_alt = any(
                player.counters.get(k, 0) >= v for k, v in skill.alt_cost.items()
            )
            if has_alt or energy_f >= float(skill.energy_cost):
                return name
        else:
            if energy_f >= float(skill.energy_cost):
                return name

        return "蓄"

    def _compute_reward(
        self,
        agent_id: int,
        agent_action_str: str,
        round_outcome: Optional[str],
        opp_energy_before: float,
        agent_smashed: Set[str],
        opp_smashed: Set[str],
        no_progress: bool,
        mirrored_stalemate: bool,
    ) -> float:
        reward = 0.0

        if round_outcome == "win":
            reward += REWARD_ROUND_WIN
        elif round_outcome == "loss":
            reward += REWARD_ROUND_LOSE
        elif not no_progress:
            reward += REWARD_DRAW

        # ── 中间塑形：粉碎 ────────────────────────────────────────────────────
        reward += len(opp_smashed) * REWARD_SMASH_ENEMY
        reward += len(agent_smashed) * REWARD_SMASH_SELF

        # ── 中间塑形：超率成功（判断 agent 本回合是否发出了"超率"动作）────────
        if agent_action_str.startswith("超率:"):
            reward += REWARD_SUPER_RATE

        # ── v2 新增：能量管理与消极行为塑形 ────────────────────────────────────

        # 判断 agent 本回合使用的技能类别
        agent_skill = SKILLS.get(agent_action_str)
        is_attack = agent_skill is not None and agent_skill.category == "attack"
        is_charge = agent_action_str == "蓄"

        # (a) 对手能量=0 时蓄能的正激励。必须看回合开始前的能量，避免把
        # “双方同时把能量花光”的镜像攻击误判为有效压制。
        if is_charge and opp_energy_before <= 0:
            reward += REWARD_CHARGE_WHEN_SAFE

        # (b) 对手能量较低时发动攻击的正激励，同样使用回合开始前状态。
        if is_attack and opp_energy_before < 1.0:
            reward += REWARD_KILL_ATTEMPT

        # (c) 消极行为惩罚：连续多回合不出攻击
        if is_attack:
            self._passive_counter = 0
        else:
            self._passive_counter += 1

        if self._passive_counter >= PASSIVE_THRESHOLD:
            reward += REWARD_PASSIVE_PENALTY

        # (d) 额外惩罚“无进展回合”，压低镜像循环的吸引力。
        if no_progress:
            reward += REWARD_STALEMATE_PENALTY
            reward += (
                max(self._no_progress_counter - 1, 0) * REWARD_STALEMATE_ESCALATION
            )
        if mirrored_stalemate:
            reward += self._mirror_counter * REWARD_MIRROR_STALEMATE

        reward += REWARD_STEP_COST

        return float(reward)

    def _award_equipment(self, winner_id: int) -> None:
        if self._players is None:
            return
        for player in self._players:
            if player.player_id == winner_id:
                equip = self.engine.grant_next_equipment(player, self._taken_equipments)
                if equip:
                    self._taken_equipments.add(equip)
                break

    def _is_match_over(self) -> bool:
        equipment_depleted = len(self._taken_equipments) >= len(EQUIPMENT_POOL)
        rounds_limit_reached = self._completed_rounds >= self._match_round_limit
        return equipment_depleted or rounds_limit_reached

    def _final_match_result(self) -> Optional[str]:
        if self._players is None:
            return "draw"
        agent_score = self._match_scores.get(self._players[0].player_id, 0)
        opp_score = self._match_scores.get(self._players[1].player_id, 0)
        if agent_score > opp_score:
            return "win"
        if agent_score < opp_score:
            return "loss"
        return "draw"

    def _match_context(self, for_agent: bool = True) -> Dict[str, float]:
        if self._players is None:
            return {
                "agent_score_norm": 0.0,
                "opp_score_norm": 0.0,
                "rounds_completed_norm": 0.0,
                "equip_remaining_norm": 1.0,
                "passive_counter_norm": 0.0,
                "no_progress_counter_norm": 0.0,
                "mirror_counter_norm": 0.0,
                "agent_policy_token": 0.0,
                "opp_policy_token": 1.0,
                "agent_prev_action_idx": ACTION_TO_IDX["蓄"],
                "opp_prev_action_idx": ACTION_TO_IDX["蓄"],
            }
        me = self._agent_player() if for_agent else self._opp_player()
        opp = self._opp_player() if for_agent else self._agent_player()
        me_score = self._match_scores.get(me.player_id, 0)
        opp_score = self._match_scores.get(opp.player_id, 0)
        rounds_norm = self._completed_rounds / max(self._match_round_limit, 1)
        equip_remaining = max(len(EQUIPMENT_POOL) - len(self._taken_equipments), 0)
        equip_norm = equip_remaining / max(len(EQUIPMENT_POOL), 1)
        passive = (
            min(self._passive_counter / max(PASSIVE_THRESHOLD, 1), 1.0)
            if for_agent
            else 0.0
        )
        no_progress = min(
            self._no_progress_counter / max(MAX_NO_PROGRESS_STREAK, 1), 1.0
        )
        mirror = min(self._mirror_counter / max(MAX_MIRROR_STREAK, 1), 1.0)
        me_prev_action = self._last_actions.get(me.player_id, "蓄")
        opp_prev_action = self._last_actions.get(opp.player_id, "蓄")
        return {
            "agent_score_norm": me_score / max(self._match_round_limit, 1),
            "opp_score_norm": opp_score / max(self._match_round_limit, 1),
            "rounds_completed_norm": rounds_norm,
            "equip_remaining_norm": equip_norm,
            "passive_counter_norm": passive,
            "no_progress_counter_norm": no_progress,
            "mirror_counter_norm": mirror,
            "agent_policy_token": self._policy_tokens.get(me.player_id, 0.0),
            "opp_policy_token": self._policy_tokens.get(opp.player_id, 1.0),
            "agent_prev_action_idx": ACTION_TO_IDX.get(
                me_prev_action, ACTION_TO_IDX["蓄"]
            ),
            "opp_prev_action_idx": ACTION_TO_IDX.get(
                opp_prev_action, ACTION_TO_IDX["蓄"]
            ),
        }

    def _agent_player(self) -> PlayerState:
        assert self._players is not None
        return self._players[self._agent_index]

    def _opp_index(self) -> int:
        return 1 - self._agent_index

    def _opp_player(self) -> PlayerState:
        assert self._players is not None
        return self._players[self._opp_index()]
