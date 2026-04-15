from __future__ import annotations

import argparse

from .agents import DEFAULT_RL_MODEL_PATH, build_agent
from .core.game_session import GameSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI entry for the Xio backend.")
    parser.add_argument(
        "--player1",
        default="rl",
        choices=["human", "simple_ai", "random", "rl"],
        help="Agent type for player 1.",
    )
    parser.add_argument(
        "--player2",
        default="rl",
        choices=["human", "simple_ai", "random", "rl"],
        help="Agent type for player 2.",
    )
    parser.add_argument(
        "--player1-name",
        default="玩家一",
        help="Display name for player 1.",
    )
    parser.add_argument(
        "--player2-name",
        default="玩家二",
        help="Display name for player 2.",
    )
    parser.add_argument(
        "--rl-model",
        default=str(DEFAULT_RL_MODEL_PATH),
        help="Path to the RL checkpoint used by rl agents.",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic inference for rl agents.",
    )
    parser.add_argument(
        "--think-time",
        type=float,
        default=0.0,
        help="Optional think time factor for the simple AI.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agents = [
        build_agent(
            args.player1,
            args.player1_name,
            rl_model_path=args.rl_model,
            deterministic=args.deterministic,
            think_time=args.think_time,
        ),
        build_agent(
            args.player2,
            args.player2_name,
            rl_model_path=args.rl_model,
            deterministic=args.deterministic,
            think_time=args.think_time,
        ),
    ]
    session = GameSession(agents=agents)
    session.start_game_loop()


if __name__ == "__main__":
    main()
