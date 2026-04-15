# Backend

This directory contains the server-side code for the Xio game. The frontend miniapp stays in `xu-miniapp/`, while the game rules, CLI, API, and reinforcement learning model are all grouped here.

## Layout

- `core/`: rule engine and match/session flow
- `agents/`: human CLI agent, simple rule AI, random AI, RL model AI, and the agent factory
- `app/`: FastAPI + WebSocket battle server
- `rl/`: training, evaluation, environment wrappers, and the saved RL checkpoint
- `requirements.txt`: unified backend dependencies

## CLI

Run a local match:

```bash
python -m backend.cli --player1 human --player2 simple_ai
```

Switch AI freely from the command line:

```bash
python -m backend.cli --player1 rl --player2 random
python -m backend.cli --player1 simple_ai --player2 rl --rl-model backend/rl/checkpoints/final_model.zip
```

Supported agent kinds:

- `human`
- `simple_ai`
- `random`
- `rl`

## API

Start the WebSocket battle server:

```bash
python -m backend.app.api
```

Optional environment variables for the built-in enemy:

```bash
BACKEND_BATTLE_AI=rl
BACKEND_BATTLE_AI_NAME=AI
BACKEND_BATTLE_RL_MODEL=backend/rl/checkpoints/final_model.zip
BACKEND_BATTLE_RL_DETERMINISTIC=true
BACKEND_BATTLE_AI_THINK_TIME=0
```

## RL

Train:

```bash
python -m backend.rl.train
```

Evaluate:

```bash
python -m backend.rl.evaluate --model backend/rl/checkpoints/final_model.zip --vs simple_ai
```
