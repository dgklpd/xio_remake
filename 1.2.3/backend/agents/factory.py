from __future__ import annotations

from pathlib import Path

from .base import PlayerAgent
from .cli_agent import HumanCLIAgent
from .rl_agent import RLModelAgent
from .rule_agents import RandomLegalAgent, SimpleAIAgent

DEFAULT_RL_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "rl" / "checkpoints" / "final_model.zip"
)


def build_agent(
    kind: str,
    name: str,
    *,
    rl_model_path: str | None = None,
    deterministic: bool = False,
    think_time: float = 0.0,
) -> PlayerAgent:
    normalized = kind.strip().lower()
    if normalized == "human":
        return HumanCLIAgent(name)
    if normalized in {"simple", "simple_ai", "ai"}:
        return SimpleAIAgent(name, think_time=think_time)
    if normalized in {"random", "random_legal"}:
        return RandomLegalAgent(name)
    if normalized == "rl":
        model_path = rl_model_path or str(DEFAULT_RL_MODEL_PATH)
        return RLModelAgent(name, model_path=model_path, deterministic=deterministic)
    raise ValueError(f"unknown agent kind: {kind}")

