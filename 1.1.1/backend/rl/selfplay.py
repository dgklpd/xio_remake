"""
model/selfplay.py
═══════════════════════════════════════════════════════════════════
自我博弈（Self-Play）核心组件。

包含两个类：
  PoolOpponent      — 从历史模型池中随机采样对手，实现对手多样性
  SelfPlayCallback  — SB3 回调，定期存档 + 更新对手池 + 胜率日志

v2 变更：
  - 集成 EpisodeStatsCollector，收集并输出每局招式分布和胜负统计
  - 通过 info["episode_stats"] 自动收集已完成 episode 的数据

自我博弈工作流：
  1. 训练开始时，对手池仅有 RandomOpponent
  2. 每隔 SELF_PLAY_UPDATE_FREQ 步：
       a. 将当前模型保存为检查点 checkpoints/step_N.zip
       b. 将此检查点加入 PoolOpponent 的池子
       c. 通过 VecEnv.env_method("set_opponent") 热更新所有训练 env 的对手
       d. 计算 vs 随机对手的胜率并记录到日志
       e. v2: 输出累计的招式分布统计报告
  3. 池子超过 SELF_PLAY_POOL_SIZE 时淘汰最旧的检查点（文件也一并删除）

关键设计：
  - 使用「70% 最新 + 30% 随机历史」的采样概率，
    防止对最新自身过拟合，同时保持对历史强策略的抗性
  - on_episode_reset() 在每局开始时刷新对手，兼顾多样性与效率
═══════════════════════════════════════════════════════════════════
"""

import random
from pathlib import Path
from typing import List, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from .config import (
    CHECKPOINT_DIR,
    SELF_PLAY_POOL_SIZE,
    SELF_PLAY_UPDATE_FREQ,
    N_EVAL_EPISODES,
    STATS_REPORT_FREQ,
    SELF_PLAY_RANDOM_OPP_PROB,
    SELF_PLAY_RULE_OPP_PROB,
)
from .env import (
    OpponentPolicy,
    RandomOpponent,
    RuleBasedOpponent,
    ModelOpponent,
    XiaoGameEnv,
)
from .stats_logger import EpisodeStatsCollector


# ═════════════════════════════════════════════════════════════════════════════
#  PoolOpponent —— 历史模型池对手
# ═════════════════════════════════════════════════════════════════════════════


class PoolOpponent(OpponentPolicy):
    """
    从历史检查点文件池中随机采样对手模型。

    采样策略：
      p_latest（默认 0.7）  ← 从最新检查点采样
      1 - p_latest          ← 从池中随机历史检查点采样

    模型在 on_episode_reset() 时延迟加载，避免每步都做磁盘 IO。
    """

    def __init__(
        self,
        pool: Optional[List[Path]] = None,
        p_latest: float = 0.70,
        p_random: float = SELF_PLAY_RANDOM_OPP_PROB,
        p_rule: float = SELF_PLAY_RULE_OPP_PROB,
    ):
        self._pool: List[Path] = pool or []
        self._p_latest = p_latest
        self._p_random = p_random
        self._p_rule = p_rule
        self._model = None  # 当前加载的模型（None 表示降级为随机）
        self._loaded_path: Optional[Path] = None
        self._engine = None
        self._players = []
        self._controlled_index = 1
        self._random_opp = RandomOpponent()
        self._rule_opp = RuleBasedOpponent()
        self._active_policy: Optional[OpponentPolicy] = self._random_opp

    # ── 池子管理 ─────────────────────────────────────────────────────────────

    def update_pool(self, new_ckpt_path: Path) -> None:
        """向池中添加新检查点，超出上限时删除最旧的文件。"""
        self._pool.append(new_ckpt_path)
        while len(self._pool) > SELF_PLAY_POOL_SIZE:
            expired = self._pool.pop(0)
            if expired.exists():
                try:
                    expired.unlink()
                except OSError:
                    pass

    # ── 主接口 ───────────────────────────────────────────────────────────────

    def on_episode_reset(self) -> None:
        """每局开始时随机采样一个历史模型并加载。"""
        draw = random.random()
        if draw < self._p_random:
            self._active_policy = self._random_opp
            self._active_policy.bind_env(
                self._engine, self._players, self._controlled_index
            )
            return
        if draw < self._p_random + self._p_rule:
            self._active_policy = self._rule_opp
            self._active_policy.bind_env(
                self._engine, self._players, self._controlled_index
            )
            self._active_policy.on_episode_reset()
            return
        if not self._pool:
            self._model = None
            self._active_policy = self._random_opp
            self._active_policy.bind_env(
                self._engine, self._players, self._controlled_index
            )
            return

        # 采样逻辑
        if random.random() < self._p_latest:
            chosen = self._pool[-1]  # 最新
        else:
            chosen = random.choice(self._pool)

        self._load_model(chosen)
        self._active_policy = None

    def predict(self, obs: np.ndarray, action_mask: np.ndarray) -> int:
        """使用当前加载的模型预测动作；模型加载失败时降级到随机。"""
        if self._active_policy is not None:
            return self._active_policy.predict(obs, action_mask)
        if self._model is None:
            valid = np.where(action_mask)[0]
            return int(np.random.choice(valid))
        try:
            action, _ = self._model.predict(
                obs[np.newaxis],
                action_masks=action_mask[np.newaxis],
                deterministic=False,
            )
            return int(action[0])
        except Exception:
            valid = np.where(action_mask)[0]
            return int(np.random.choice(valid))

    def bind_env(self, engine, players, controlled_index: int = 1) -> None:
        self._engine = engine
        self._players = players
        self._controlled_index = controlled_index
        self._random_opp.bind_env(engine, players, controlled_index)
        self._rule_opp.bind_env(engine, players, controlled_index)
        if self._active_policy is not None:
            self._active_policy.bind_env(engine, players, controlled_index)

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _load_model(self, path: Path) -> None:
        """从磁盘加载 MaskablePPO 检查点。加载失败时静默降级。"""
        if self._loaded_path == path and self._model is not None:
            return
        try:
            from sb3_contrib import MaskablePPO

            self._model = MaskablePPO.load(str(path), device="cpu")
            self._loaded_path = path
        except Exception:
            self._model = None
            self._loaded_path = None


# ═════════════════════════════════════════════════════════════════════════════
#  SelfPlayCallback —— SB3 自我博弈回调
# ═════════════════════════════════════════════════════════════════════════════


class SelfPlayCallback(BaseCallback):
    """
    每隔 `update_freq` 步执行：
      1. 将当前模型存档到 CHECKPOINT_DIR/step_{N}.zip
      2. 更新 PoolOpponent 的历史模型池
      3. 通过 env_method 热更新所有并行训练 env 的对手
      4. 计算并打印 vs 随机对手的胜率（便于监控训练进度）
      5. v2: 输出累计的招式分布统计报告
    """

    def __init__(
        self,
        pool_opponent: PoolOpponent,
        update_freq: int = SELF_PLAY_UPDATE_FREQ,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self._pool_opp = pool_opponent
        self._update_freq = update_freq
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

        # v2: 招式分布统计收集器
        self._stats = EpisodeStatsCollector()

    def _on_step(self) -> bool:
        # v2: 从 info 中收集已完成 episode 的统计数据
        self._collect_episode_stats()

        if self.n_calls % self._update_freq == 0:
            self._save_and_update()
        return True

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _collect_episode_stats(self) -> None:
        """从 VecEnv 的 info 中提取已完成 episode 的统计数据。"""
        infos = self.locals.get("infos", [])
        for info in infos:
            ep_stats = info.get("episode_stats")
            if ep_stats is None:
                continue
            self._stats.record_episode(
                agent_action_counts=ep_stats["agent_action_counts"],
                opp_action_counts=ep_stats["opp_action_counts"],
                result=ep_stats["result"],
                n_rounds=ep_stats["n_rounds"],
            )

        # 每累计 STATS_REPORT_FREQ 局，输出一次报告
        if self._stats.total_episodes >= STATS_REPORT_FREQ:
            report = self._stats.report_and_reset(
                label=f"(Step {self.num_timesteps:,})"
            )
            print(report)

    def _save_and_update(self) -> None:
        # 1. 存档当前模型
        ckpt_path = CHECKPOINT_DIR / f"step_{self.num_timesteps}.zip"
        self.model.save(str(ckpt_path))

        # 2. 更新池子
        self._pool_opp.update_pool(ckpt_path)

        if self.verbose:
            print(
                f"\n[SelfPlay] Step {self.num_timesteps:,} | "
                f"Saved {ckpt_path.name} | "
                f"Pool size={len(self._pool_opp._pool)}"
            )

        # 3. 热更新所有训练 env 的对手
        # 重新广播当前最新的池对象（包含新增的检查点）
        try:
            self.training_env.env_method("set_opponent", self._pool_opp)
        except Exception as e:
            if self.verbose:
                print(f"[SelfPlay] Warning: 对手更新失败 — {e}")

        # 4. 评估当前模型 vs 随机对手，记录大致胜率
        random_eval = self._quick_eval()
        mirror_truncation = self._mirror_eval()
        if self.verbose:
            print(
                "[SelfPlay] vs RandomOpponent "
                f"胜率 = {random_eval['win_rate']:.1%} | "
                f"超时率 = {random_eval['truncation_rate']:.1%}"
            )
            print(f"[SelfPlay] vs Self 截断率 = {mirror_truncation:.1%}\n")

        # 5. v2: 如果有未输出的统计，强制输出一次
        if self._stats.total_episodes > 0:
            report = self._stats.report_and_reset(
                label=f"(Step {self.num_timesteps:,}, checkpoint)"
            )
            print(report)

    def _quick_eval(self, n_episodes: int = 100) -> dict:
        """快速评估：让当前模型对随机对手打 n_episodes 局，返回胜率与超时率。"""
        env = XiaoGameEnv(opponent=RandomOpponent())
        wins = losses = truncated = 0

        for _ in range(n_episodes):
            obs, _ = env.reset()
            done = False
            while not done:
                masks = env.action_masks()
                action, _ = self.model.predict(
                    obs, action_masks=masks, deterministic=True
                )
                obs, _, terminated, step_truncated, info = env.step(int(action))
                done = terminated or step_truncated

            result = info.get("match_result")
            if result == "truncated":
                truncated += 1
            elif result == "win":
                wins += 1
            elif result == "loss":
                losses += 1
            else:
                dead = info.get("dead_players", set())
                if 1 not in dead and dead:
                    wins += 1
                elif 1 in dead:
                    losses += 1

        decisive = wins + losses
        return {
            "win_rate": wins / decisive if decisive > 0 else 0.5,
            "truncation_rate": truncated / max(n_episodes, 1),
        }

    def _mirror_eval(self, n_episodes: int = 20) -> float:
        """部署向快速诊断：当前模型与自身对打时的截断率。"""
        env = XiaoGameEnv(opponent=ModelOpponent(self.model))
        truncated = 0

        for _ in range(n_episodes):
            obs, _ = env.reset()
            done = False
            while not done:
                masks = env.action_masks()
                action, _ = self.model.predict(
                    obs, action_masks=masks, deterministic=True
                )
                obs, _, terminated, step_truncated, info = env.step(int(action))
                done = terminated or step_truncated
            if info.get("match_result") == "truncated":
                truncated += 1

        return truncated / max(n_episodes, 1)
