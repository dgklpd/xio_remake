"""
model/obs.py
═══════════════════════════════════════════════════════════════════
观测空间编码器 + 动作掩码生成器。

核心函数：
  encode_player(player)          -> np.ndarray  单玩家状态向量
  encode_obs(agent, opponent)    -> np.ndarray  完整观测（自+对手）
  get_action_mask(engine, player)-> np.ndarray  当前回合合法动作掩码

设计原则：
  - 所有特征归一化到 [0, 1]，与 PPO 的期望输入分布匹配
  - 动作掩码通过 rules.py 的 available_skills / super_rate_candidates
    动态生成，完全和引擎规则同步，不存在硬编码的特判逻辑
═══════════════════════════════════════════════════════════════════
"""


from typing import Dict

import numpy as np

from ..core.rules import PlayerState, RuleEngine
from .config import (
    EQUIPMENT_POOL,
    EQUIP_TO_IDX,
    SKILL_TO_IDX,
    N_SKILLS,
    N_EQUIPMENTS,
    COUNTER_KEYS,
    ENERGY_NORM,
    CHARGE_BONUS_NORM,
    COUNTER_NORM,
    PHASE_NORM,
    OBS_PER_PLAYER,
    ACTION_TO_IDX,
    N_ACTIONS,
    SUPER_RATE_NAMES,
    MATCH_CONTEXT_DIM,
    PREV_ACTIONS_DIM,
)


def encode_player(player: PlayerState) -> np.ndarray:
    """
    将单个玩家的 PlayerState 编码为定长 float32 向量。

    向量结构（共 OBS_PER_PLAYER 维）：
      [0]          energy（归一化）
      [1]          charge_bonus（归一化）
      [2:9]        has_equipment（7 位二值，是否拥有各装备）
      [9:16]       phase_norm（7 位，各装备当前阶段归一化）
      [16:19]      counters（3 位，爆冰/爆龙/晶冰层数归一化）
      [19:57]      smashed_skills（38 位二值，本小局内被粉碎的技能掩码）
      [57:59]      welfare（2 位，是否拥有锁链*1 / 小盾低保）
    """
    vec = np.zeros(OBS_PER_PLAYER, dtype=np.float32)
    ptr = 0

    # ── 1. 蓄能量（clip 后归一化）────────────────────────────────────────────
    vec[ptr] = min(float(player.energy) / ENERGY_NORM, 1.0)
    ptr += 1

    # ── 2. 锁链总加成（归一化）───────────────────────────────────────────────
    vec[ptr] = player.charge_bonus / CHARGE_BONUS_NORM
    ptr += 1

    # ── 3. 装备持有标志（7 位 one-hot）───────────────────────────────────────
    for i, equip in enumerate(EQUIPMENT_POOL):
        vec[ptr + i] = 1.0 if equip in player.equipments else 0.0
    ptr += N_EQUIPMENTS

    # ── 4. 装备阶段（7 位，按各装备 max_phase 独立归一化）────────────────────
    for i, equip in enumerate(EQUIPMENT_POOL):
        if equip in player.equipments:
            phase = player.equipments[equip].phase
            vec[ptr + i] = phase / PHASE_NORM[equip]
    ptr += N_EQUIPMENTS

    # ── 5. 特殊能量层数（3 位）───────────────────────────────────────────────
    for i, key in enumerate(COUNTER_KEYS):
        vec[ptr + i] = min(player.counters.get(key, 0) / COUNTER_NORM, 1.0)
    ptr += 3

    # ── 6. 被粉碎技能掩码（38 位）────────────────────────────────────────────
    # 被粉碎技能在本小局内无法使用，AI 需要感知到这一限制
    for skill_name in player.smashed_skills:
        idx = SKILL_TO_IDX.get(skill_name)
        if idx is not None:
            vec[ptr + idx] = 1.0
    ptr += N_SKILLS

    # ── 7. 低保状态标志（2 位）───────────────────────────────────────────────
    vec[ptr] = 1.0 if "锁链*1" in player.welfare else 0.0
    vec[ptr + 1] = 1.0 if "小盾" in player.welfare else 0.0
    ptr += 2

    assert ptr == OBS_PER_PLAYER, f"编码维度错误: ptr={ptr}, expected={OBS_PER_PLAYER}"
    return vec


def encode_obs(
    agent: PlayerState,
    opponent: PlayerState,
    context: Dict[str, float],
) -> np.ndarray:
    """组合自身、对手以及对局上下文组成完整观测。"""
    ctx_vec = np.zeros(MATCH_CONTEXT_DIM, dtype=np.float32)
    keys = (
        "agent_score_norm",
        "opp_score_norm",
        "rounds_completed_norm",
        "equip_remaining_norm",
        "passive_counter_norm",
        "no_progress_counter_norm",
        "mirror_counter_norm",
        "agent_policy_token",
        "opp_policy_token",
    )
    for i, key in enumerate(keys):
        ctx_vec[i] = float(context.get(key, 0.0))

    prev_actions_vec = np.zeros(PREV_ACTIONS_DIM, dtype=np.float32)
    agent_prev_idx = int(context.get("agent_prev_action_idx", -1))
    opp_prev_idx = int(context.get("opp_prev_action_idx", -1))
    if 0 <= agent_prev_idx < N_ACTIONS:
        prev_actions_vec[agent_prev_idx] = 1.0
    if 0 <= opp_prev_idx < N_ACTIONS:
        prev_actions_vec[N_ACTIONS + opp_prev_idx] = 1.0

    return np.concatenate(
        [encode_player(agent), encode_player(opponent), ctx_vec, prev_actions_vec]
    )


def get_action_mask(engine: RuleEngine, player: PlayerState) -> np.ndarray:
    """
    生成该玩家本回合的合法动作掩码（True = 当前可用）。

    掩码完全基于 RuleEngine 的 available_skills / super_rate_candidates，
    与底层规则保持强同步，任何规则变更都会自动反映到掩码中。

    处理顺序：
      1. 普通技能：通过 available_skills 获取，并检查能量是否满足（含替代消耗）
      2. 超率动作：通过 super_rate_candidates 获取，并检查 energy >= 3
      3. 保底：无论如何，"蓄" 始终为合法（energy_cost=0，永远可用）
    """
    mask = np.zeros(N_ACTIONS, dtype=bool)

    # ── 1. 普通技能 ───────────────────────────────────────────────────────────
    available = engine.available_skills(player)
    energy_f = float(player.energy)

    for name, skill in available.items():
        idx = ACTION_TO_IDX.get(name)
        if idx is None:
            continue  # 未知技能（不在固定列表中），跳过

        # 能量足够判断：优先检查替代消耗（爆冰、晶冰等），再检查常规蓄能
        if skill.alt_cost:
            can_pay = any(
                player.counters.get(k, 0) >= v for k, v in skill.alt_cost.items()
            )
            # 替代消耗不足时，回退检查常规蓄能
            if not can_pay:
                can_pay = energy_f >= float(skill.energy_cost)
        else:
            can_pay = energy_f >= float(skill.energy_cost)

        if can_pay:
            mask[idx] = True

    # ── 2. 超率动作 ───────────────────────────────────────────────────────────
    if energy_f >= 3.0:
        for equip_name in engine.super_rate_candidates(player):
            action_name = f"超率:{equip_name}"
            idx = ACTION_TO_IDX.get(action_name)
            if idx is not None:
                mask[idx] = True

    # ── 3. 保底：蓄永远合法 ──────────────────────────────────────────────────
    mask[ACTION_TO_IDX["蓄"]] = True

    return mask
