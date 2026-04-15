"""
model/train.py  ← 训练入口文件（推送到服务器后直接运行此文件）
═══════════════════════════════════════════════════════════════════
使用 MaskablePPO（sb3-contrib）+ 自我博弈（Self-Play）训练拍手游戏 AI。

配置方式（命令行参数）：
  python model/train.py                        # 默认配置快速启动
  python model/train.py --n_envs 16 --device cuda  # 服务器多核 + GPU
  python model/train.py --resume               # 从上次检查点断点续训

训练阶段：
  Phase 1 [0 ~ 总步数] : 纯自我博弈（对手始终来自历史模型池）

检查点输出目录：
  model/checkpoints/                 # 自我博弈历史存档（定期清理）
  model/checkpoints/best/            # 对随机对手评估最佳模型
  model/checkpoints/final_model.zip  # 最终模型
═══════════════════════════════════════════════════════════════════
"""

import argparse
from pathlib import Path

from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import EvalCallback, CallbackList
from sb3_contrib import MaskablePPO

from .config import (
    PPO_KWARGS,
    CHECKPOINT_DIR,
    N_EVAL_EPISODES,
    SELF_PLAY_UPDATE_FREQ,
    OBS_DIM,
)
from .env import RandomOpponent, XiaoGameEnv
from .selfplay import PoolOpponent, SelfPlayCallback


# ─── 环境工厂函数（供 VecEnv 使用）──────────────────────────────────────────


def _make_env(opponent=None):
    """返回一个无参数的环境构造函数（VecEnv 要求 callable）。"""

    def _init():
        return XiaoGameEnv(opponent=opponent or RandomOpponent())

    return _init


# ─── 主训练函数 ──────────────────────────────────────────────────────────────


def main(args: argparse.Namespace) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    best_dir = CHECKPOINT_DIR / "best"
    best_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" 拍手游戏 RL 训练启动")
    print(f"  device        = {args.device}")
    print(f"  n_envs        = {args.n_envs}")
    print(f"  total_steps   = {args.total_timesteps:,}")
    print(f"  resume        = {args.resume}")
    print("=" * 60)

    # ── 1. 初始化自我博弈对手池 ─────────────────────────────────────────────
    pool_opp = PoolOpponent(p_latest=0.70)
    initial_opp = pool_opp

    # ── 2. 构建训练环境 ─────────────────────────────────────────────────────
    print(f"\n正在创建 {args.n_envs} 个并行训练环境...")
    env_fns = [_make_env(initial_opp) for _ in range(args.n_envs)]

    # Windows 使用 DummyVecEnv（spawn 限制），Linux 服务器推荐 SubprocVecEnv
    if args.n_envs > 1 and sys.platform != "win32":
        vec_env = SubprocVecEnv(env_fns)
        print("  → SubprocVecEnv（多进程并行）")
    else:
        vec_env = DummyVecEnv(env_fns)
        print("  → DummyVecEnv（单进程，Windows 兼容）")

    # ── 3. 评估环境（始终对随机对手，保证评估稳定性）─────────────────────────
    eval_env = DummyVecEnv([_make_env(RandomOpponent())])

    # ── 4. 创建或恢复模型 ───────────────────────────────────────────────────
    latest_ckpt = CHECKPOINT_DIR / "latest.zip"
    if args.resume and latest_ckpt.exists():
        probe_model = MaskablePPO.load(str(latest_ckpt))
        ckpt_obs_dim = int(probe_model.observation_space.shape[0])
        if ckpt_obs_dim != OBS_DIM:
            raise RuntimeError(
                "latest.zip 与当前训练代码的观测维度不兼容："
                f"checkpoint={ckpt_obs_dim}, current={OBS_DIM}。"
                "请删除旧 checkpoint 后重新训练。"
            )
        print(f"\n从检查点恢复：{latest_ckpt}")
        model = MaskablePPO.load(str(latest_ckpt), env=vec_env)
    else:
        print("\n从头初始化 MaskablePPO 模型...")
        model = MaskablePPO(
            "MlpPolicy",
            vec_env,
            device=args.device,
            **PPO_KWARGS,
        )

    # ── 5. 纯自博弈训练：先把当前模型存成池子种子 ──────────────────────────
    if args.resume:
        pool_opp.update_pool(latest_ckpt)
    else:
        bootstrap_ckpt = CHECKPOINT_DIR / "bootstrap_selfplay.zip"
        model.save(str(bootstrap_ckpt))
        pool_opp.update_pool(bootstrap_ckpt)

    try:
        vec_env.env_method("set_opponent", pool_opp)
    except Exception:
        pass

    print(f"\n[Phase 1] 纯自我博弈训练 {args.total_timesteps:,} 步...")

    # 回调列表
    selfplay_cb = SelfPlayCallback(
        pool_opponent=pool_opp,
        update_freq=SELF_PLAY_UPDATE_FREQ,
        verbose=1,
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(best_dir),
        log_path=str(CHECKPOINT_DIR / "eval_logs"),
        n_eval_episodes=N_EVAL_EPISODES,
        eval_freq=args.eval_freq,
        deterministic=True,
        verbose=1,
    )

    model.learn(
        total_timesteps=args.total_timesteps,
        callback=CallbackList([selfplay_cb, eval_cb]),
        reset_num_timesteps=not args.resume,
    )

    # ── 7. 保存最终模型 ─────────────────────────────────────────────────────
    final_path = CHECKPOINT_DIR / "final_model"
    model.save(str(final_path))
    # 同时保存为 latest.zip 供下次 --resume 使用
    model.save(str(CHECKPOINT_DIR / "latest"))

    print("\n" + "=" * 60)
    print(f" 训练完成！最终模型已保存至：")
    print(f"   {final_path}.zip")
    print("=" * 60)


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="拍手游戏 RL 训练脚本（MaskablePPO + Self-Play）"
    )
    parser.add_argument(
        "--n_envs",
        type=int,
        default=8,
        help="并行训练环境数量（默认 8）",
    )
    parser.add_argument(
        "--total_timesteps",
        type=int,
        default=1_000_000,
        help="总训练步数（与 n_envs 无关，是 env-step 总量）",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="训练设备（auto 表示有 GPU 则用 GPU）",
    )
    parser.add_argument(
        "--eval_freq",
        type=int,
        default=50_000,
        help="EvalCallback 的评估频率（单位：env-step）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 checkpoints/latest.zip 断点续训",
    )

    args = parser.parse_args()
    main(args)
