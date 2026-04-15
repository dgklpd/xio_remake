"""
model/evaluate.py
═══════════════════════════════════════════════════════════════════
评估训练好的 RL 智能体对抗各种对手的胜率。

支持的评估场景：
  1. vs 随机对手         （基准）
  2. vs SimpleAIAgent    （手工规则 AI）
  3. vs 任意其他 MaskablePPO 模型

用法：
  python model/evaluate.py --model model/checkpoints/final_model.zip
  python model/evaluate.py --model best --vs simple_ai --n_episodes 500
═══════════════════════════════════════════════════════════════════
"""

import argparse
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO

from .config import CHECKPOINT_DIR, N_EVAL_EPISODES, OBS_DIM
from .env import ModelOpponent, RandomOpponent, RuleBasedOpponent, XiaoGameEnv


# ─── 核心评估函数 ─────────────────────────────────────────────────────────────


def evaluate_model(
    model: MaskablePPO,
    opponent_name: str = "random",
    n_episodes: int = N_EVAL_EPISODES,
    opponent_model: MaskablePPO = None,
) -> dict:
    """
    对指定对手跑 n_episodes 局，统计胜/负/平。

    参数：
      model          : 待评估的 MaskablePPO 模型
      opponent_name  : "random" | "simple_ai" | "model"
      n_episodes     : 评估局数
      opponent_model : 当 opponent_name=="model" 时传入对手模型

    返回：
      {"wins": int, "losses": int, "draws": int, "win_rate": float}
    """
    # 构建对手
    if opponent_name == "random":
        opponent = RandomOpponent()
    elif opponent_name == "model" and opponent_model is not None:
        opponent = ModelOpponent(opponent_model)
    elif opponent_name == "simple_ai":
        opponent = RuleBasedOpponent()
    else:
        raise ValueError(f"未知对手类型：{opponent_name}")

    env = XiaoGameEnv(opponent=opponent)
    wins = losses = draws = truncated = 0

    for ep in range(n_episodes):
        obs, _ = env.reset()
        done = False

        while not done:
            masks = env.action_masks()
            action, _ = model.predict(obs, action_masks=masks, deterministic=True)
            obs, _, terminated, step_truncated, info = env.step(int(action))
            done = terminated or step_truncated

        match_result = info.get("match_result")
        if match_result == "draw":
            draws += 1
        elif match_result == "win":
            wins += 1
        elif match_result == "loss":
            losses += 1
        elif match_result == "truncated":
            truncated += 1
        else:
            dead = info.get("dead_players", set())
            if 1 not in dead and dead:
                wins += 1
            elif 1 in dead:
                losses += 1

        if (ep + 1) % max(n_episodes // 10, 1) == 0:
            total_so_far = wins + losses + draws + truncated
            wr = wins / total_so_far if total_so_far else 0
            print(
                f"  [{ep + 1}/{n_episodes}] 胜率 = {wr:.1%}  "
                f"(W:{wins} L:{losses} D:{draws} T:{truncated})"
            )

    total = wins + losses + draws + truncated
    win_rate = wins / total if total > 0 else 0.0

    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "truncated": truncated,
        "win_rate": win_rate,
    }


def print_eval_result(result: dict, opponent_name: str) -> None:
    total = result["wins"] + result["losses"] + result["draws"] + result["truncated"]
    print("\n" + "=" * 50)
    print(f" 评估结果（vs {opponent_name}，共 {total} 局）")
    print(f"  胜   : {result['wins']}  ({100 * result['wins'] / max(total, 1):.1f}%)")
    print(
        f"  负   : {result['losses']}  ({100 * result['losses'] / max(total, 1):.1f}%)"
    )
    print(f"  平   : {result['draws']}  ({100 * result['draws'] / max(total, 1):.1f}%)")
    print(
        f"  超时 : {result['truncated']}  ({100 * result['truncated'] / max(total, 1):.1f}%)"
    )
    print(f"  胜率  : {result['win_rate']:.1%}")
    print("=" * 50 + "\n")


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="评估拍手游戏 RL 模型")
    parser.add_argument(
        "--model",
        type=str,
        default=str(CHECKPOINT_DIR / "best" / "best_model.zip"),
        help="模型路径（.zip 文件，或 'best' 表示自动查找最优检查点）",
    )
    parser.add_argument(
        "--vs",
        type=str,
        default="random",
        choices=["random", "simple_ai", "model"],
        help="对手类型",
    )
    parser.add_argument(
        "--vs_model",
        type=str,
        default=None,
        help="当 --vs=model 时，指定对手模型路径",
    )
    parser.add_argument(
        "--n_episodes",
        type=int,
        default=N_EVAL_EPISODES,
        help="评估局数",
    )
    args = parser.parse_args()

    # 自动处理 "best" 关键字
    model_path = Path(args.model)
    if not model_path.exists():
        # 尝试加 .zip 后缀
        model_path = model_path.with_suffix(".zip")
    if not model_path.exists():
        print(f"错误：找不到模型文件：{model_path}")
        sys.exit(1)

    print(f"\n加载模型：{model_path}")
    model = MaskablePPO.load(str(model_path))
    ckpt_obs_dim = int(model.observation_space.shape[0])
    if ckpt_obs_dim != OBS_DIM:
        print(
            "错误：当前评估代码与模型观测维度不兼容："
            f"checkpoint={ckpt_obs_dim}, current={OBS_DIM}。"
            "请基于当前代码重新训练模型后再评估。"
        )
        sys.exit(1)

    # 加载对手模型（仅 --vs=model 时需要）
    opp_model = None
    if args.vs == "model":
        if args.vs_model is None:
            print("错误：--vs=model 时必须指定 --vs_model 路径")
            sys.exit(1)
        opp_model = MaskablePPO.load(args.vs_model)

    print(f"评估对手：{args.vs}，局数：{args.n_episodes}")
    result = evaluate_model(model, args.vs, args.n_episodes, opp_model)
    print_eval_result(result, args.vs)
