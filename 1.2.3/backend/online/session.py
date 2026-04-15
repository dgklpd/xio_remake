from __future__ import annotations

import asyncio
import contextlib
import importlib
import time
from typing import Any, Awaitable, Callable

from fastapi import WebSocket

from ..core.rules import EquipmentState, PlayerState, RoundResult, RuleEngine, create_players
from .models import RoomSeat, RoomSeatState, RoomStateView, RoomStatus
from .service import OnlineRoomService, RoomNotFoundError

ROUND_SECONDS = 15
LOCKED_CARD_PREVIEW_SECONDS = 0.45
REVEAL_DELAY_SECONDS = 2.2
MATCH_SMALL_GAME_LIMIT = 30
DISCONNECT_GRACE_SECONDS = 0


class RoomSession:
    def __init__(
        self,
        service: OnlineRoomService,
        room_state: RoomStateView,
        *,
        on_room_closed: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        self.service = service
        self.room_code = room_state.room_code
        self._state = room_state
        self._on_room_closed = on_room_closed
        self._lock = asyncio.Lock()
        self._connections: dict[RoomSeat, WebSocket | None] = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }

        self.engine: RuleEngine | None = None
        self.players: dict[RoomSeat, PlayerState] = {}
        self.scores: dict[RoomSeat, int] = {
            RoomSeat.HOST: 0,
            RoomSeat.GUEST: 0,
        }
        self.taken_equipments: set[str] = set()
        self.small_games_completed: int = 0
        self.small_game_limit: int = MATCH_SMALL_GAME_LIMIT
        self.round_index: int = 1
        self.round_deadline_ts: int | None = None
        self.round_seconds: int = ROUND_SECONDS
        self.locked_card_preview_seconds: float = LOCKED_CARD_PREVIEW_SECONDS
        self.reveal_delay_seconds: float = REVEAL_DELAY_SECONDS
        self.disconnect_grace_seconds: float = DISCONNECT_GRACE_SECONDS
        self.declared_actions: dict[RoomSeat, str | None] = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }
        self.played_card_ids: dict[RoomSeat, str | None] = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }
        self.card_ready: dict[RoomSeat, bool] = {
            RoomSeat.HOST: False,
            RoomSeat.GUEST: False,
        }
        self.reveal_cards: bool = False
        self.resolution: dict[str, Any] | None = None
        self.timeout_task: asyncio.Task[None] | None = None
        self.resolve_task: asyncio.Task[None] | None = None
        self.advance_task: asyncio.Task[None] | None = None
        self.disconnect_tasks: dict[RoomSeat, asyncio.Task[None] | None] = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }
        self.disconnect_deadlines: dict[RoomSeat, int | None] = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }

    @property
    def state(self) -> RoomStateView:
        return self._state

    @property
    def has_active_battle(self) -> bool:
        return self.engine is not None and bool(self.players)

    @property
    def is_ready_to_start(self) -> bool:
        guest = self._state.guest
        return bool(
            guest
            and self._state.host.ready
            and guest.ready
            and self._state.status in {RoomStatus.WAITING, RoomStatus.FULL}
        )

    def _battle_api(self):
        return importlib.import_module("backend.app.api")

    def _seat_state_locked(self, seat: RoomSeat) -> RoomSeatState | None:
        if seat is RoomSeat.HOST:
            return self._state.host
        return self._state.guest

    def _other_seat(self, seat: RoomSeat) -> RoomSeat:
        return RoomSeat.GUEST if seat is RoomSeat.HOST else RoomSeat.HOST

    def _serialize_room_state_locked(self) -> dict[str, Any]:
        guest = self._state.guest
        can_start = bool(
            guest
            and self._state.host.ready
            and guest.ready
            and self._state.status in {RoomStatus.WAITING, RoomStatus.FULL}
        )
        return {
            "room_code": self._state.room_code,
            "room_name": self._state.room_name,
            "status": self._state.status.value,
            "created_at": self._state.created_at,
            "updated_at": self._state.updated_at,
            "expires_at": self._state.expires_at,
            "host": self._serialize_seat_public_locked(self._state.host),
            "guest": self._serialize_seat_public_locked(guest),
            "can_start": can_start,
        }

    def _serialize_seat_public_locked(self, seat: RoomSeatState | None) -> dict[str, Any] | None:
        if seat is None:
            return None
        return {
            "seat": seat.seat.value,
            "user_id": seat.user_id,
            "display_name": seat.display_name,
            "avatar_url": seat.avatar_url,
            "connected": seat.connected,
            "ready": seat.ready,
        }

    def _default_action_name(self) -> str:
        battle_api = self._battle_api()
        return battle_api.CARD_ID_TO_NAME["xu"]

    def _reset_small_round_state_locked(self) -> None:
        if not self.players or self.engine is None:
            return
        for player in self.players.values():
            player.small_round_reset()
        self.engine.apply_welfare_if_needed(tuple(self.players.values()))
        self.round_index = 1

    def _clear_round_runtime_locked(self) -> None:
        self.round_deadline_ts = None
        self.declared_actions = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }
        self.played_card_ids = {
            RoomSeat.HOST: None,
            RoomSeat.GUEST: None,
        }
        self.card_ready = {
            RoomSeat.HOST: False,
            RoomSeat.GUEST: False,
        }
        self.reveal_cards = False
        self.resolution = None

    def _consume_round_tasks_locked(self) -> list[asyncio.Task[Any]]:
        tasks = [task for task in (self.timeout_task, self.resolve_task, self.advance_task) if task]
        self.timeout_task = None
        self.resolve_task = None
        self.advance_task = None
        return tasks

    def _consume_timeout_task_locked(self) -> asyncio.Task[Any] | None:
        task = self.timeout_task
        self.timeout_task = None
        return task

    def _consume_disconnect_tasks_locked(
        self,
        *,
        exclude: set[RoomSeat] | None = None,
    ) -> list[asyncio.Task[Any]]:
        exclude = exclude or set()
        tasks: list[asyncio.Task[Any]] = []
        for seat in (RoomSeat.HOST, RoomSeat.GUEST):
            if seat in exclude:
                continue
            task = self.disconnect_tasks[seat]
            if task is not None:
                tasks.append(task)
            self.disconnect_tasks[seat] = None
            self.disconnect_deadlines[seat] = None
        return tasks

    async def _cancel_disconnect_task_for_seat(self, seat: RoomSeat) -> None:
        task: asyncio.Task[Any] | None = None
        async with self._lock:
            task = self.disconnect_tasks[seat]
            self.disconnect_tasks[seat] = None
            self.disconnect_deadlines[seat] = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _cancel_tasks(self, tasks: list[asyncio.Task[Any]]) -> None:
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _stop_battle_runtime(self) -> None:
        async with self._lock:
            tasks = self._consume_round_tasks_locked()
            tasks.extend(self._consume_disconnect_tasks_locked())
            self.engine = None
            self.players = {}
            self._clear_round_runtime_locked()
            self.scores = {
                RoomSeat.HOST: 0,
                RoomSeat.GUEST: 0,
            }
            self.small_games_completed = 0
            self.taken_equipments.clear()
        await self._cancel_tasks(tasks)

    async def _notify_manager_closed(self) -> None:
        if self._on_room_closed is None:
            return
        result = self._on_room_closed(self.room_code)
        if asyncio.iscoroutine(result):
            await result

    def _build_connection_event_locked(self, action: str, seat: RoomSeat) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "seat": seat.value,
            "room_code": self.room_code,
        }
        deadline = self.disconnect_deadlines.get(seat)
        if deadline is not None:
            payload["reconnect_deadline_ts"] = deadline
            payload["grace_seconds"] = self.disconnect_grace_seconds
        return {"action": action, "payload": payload}

    async def refresh(self) -> RoomStateView:
        async with self._lock:
            self._state = await self.service.get_room_state(self.room_code)
            return self._state

    async def set_ready(self, seat: RoomSeat, ready: bool) -> RoomStateView:
        async with self._lock:
            self._state = await self.service.set_ready(self.room_code, seat, ready)
            room_message = {"action": "room_state", "state": self._serialize_room_state_locked()}
            targets = self._connected_targets_locked()
        await self._broadcast_messages(targets, room_message)
        return self._state

    async def leave(self, seat: RoomSeat) -> RoomStateView | None:
        async with self._lock:
            next_state = await self.service.leave_room(self.room_code, seat)
            if next_state is None:
                targets = self._connected_targets_locked()
                close_targets = list(targets)
                self._connections = {RoomSeat.HOST: None, RoomSeat.GUEST: None}
                tasks = self._consume_round_tasks_locked()
                tasks.extend(self._consume_disconnect_tasks_locked())
            else:
                self._state = next_state
                room_message = {"action": "room_state", "state": self._serialize_room_state_locked()}
                targets = self._connected_targets_locked()
                close_targets = []
                tasks = self._consume_round_tasks_locked()
                tasks.extend(self._consume_disconnect_tasks_locked())
                self.engine = None
                self.players = {}
                self._clear_round_runtime_locked()
        await self._cancel_tasks(tasks)
        if next_state is None:
            await self._broadcast_messages(
                close_targets,
                {"action": "room_closed", "payload": {"reason": "player_left", "seat": seat.value}},
            )
            await self._close_websockets(close_targets)
            await self._notify_manager_closed()
            return None
        await self._broadcast_messages(targets, room_message)
        return self._state

    async def close(self) -> None:
        async with self._lock:
            await self.service.close_room(self.room_code)
            targets = self._connected_targets_locked()
            self._connections = {RoomSeat.HOST: None, RoomSeat.GUEST: None}
            tasks = self._consume_round_tasks_locked()
            tasks.extend(self._consume_disconnect_tasks_locked())
            self.engine = None
            self.players = {}
            self._clear_round_runtime_locked()
        await self._cancel_tasks(tasks)
        await self._broadcast_messages(targets, {"action": "room_closed", "payload": {"reason": "room_closed"}})
        await self._close_websockets(targets)
        await self._notify_manager_closed()

    async def authenticate(self, seat: RoomSeat, session_token: str) -> None:
        async with self._lock:
            self._state = await self.service.get_room_state(self.room_code)
            seat_state = self._seat_state_locked(seat)
            if seat_state is None or seat_state.token != session_token:
                raise PermissionError("invalid session token")

    async def register_connection(self, seat: RoomSeat, session_token: str, websocket: WebSocket) -> None:
        previous: WebSocket | None = None
        async with self._lock:
            self._state = await self.service.get_room_state(self.room_code)
            seat_state = self._seat_state_locked(seat)
            if seat_state is None or seat_state.token != session_token:
                raise PermissionError("invalid session token")

            previous = self._connections.get(seat)
            self._connections[seat] = websocket
            self._state = await self.service.set_connection_state(self.room_code, seat, True)
            room_message = {"action": "room_state", "state": self._serialize_room_state_locked()}
            initial_battle = None
            if self.has_active_battle:
                initial_battle = {
                    "action": "battle_state",
                    "state": self._serialize_battle_state_for_locked(seat),
                }
            other_targets = self._connected_targets_locked(exclude={seat})

        if previous is not None and previous is not websocket:
            with contextlib.suppress(Exception):
                await previous.close(code=4000)
        await self._safe_send_json(websocket, room_message)
        if initial_battle is not None:
            await self._safe_send_json(websocket, initial_battle)
        await self._broadcast_messages(other_targets, room_message)

    async def unregister_connection(self, seat: RoomSeat, websocket: WebSocket) -> None:
        async with self._lock:
            current = self._connections.get(seat)
            if current is not websocket:
                return
            self._connections[seat] = None
            targets = self._connected_targets_locked()
            tasks = self._consume_round_tasks_locked()
            tasks.extend(self._consume_disconnect_tasks_locked())
            self._connections = {RoomSeat.HOST: None, RoomSeat.GUEST: None}
            self.engine = None
            self.players = {}
            self._clear_round_runtime_locked()
        await self._cancel_tasks(tasks)
        await self._broadcast_messages(
            targets,
            {"action": "room_closed", "payload": {"reason": "player_disconnected", "seat": seat.value}},
        )
        await self._close_websockets(targets)
        await self.service.close_room(self.room_code)
        await self._notify_manager_closed()

    async def start_battle_if_ready(self) -> bool:
        async with self._lock:
            if self.has_active_battle or not self.is_ready_to_start:
                return False

            tasks = self._consume_round_tasks_locked()
            self._state = await self.service.set_room_status(self.room_code, RoomStatus.PLAYING)

            players = create_players(2)
            self.engine = RuleEngine()
            self.players = {
                RoomSeat.HOST: players[0],
                RoomSeat.GUEST: players[1],
            }
            self.scores = {
                RoomSeat.HOST: 0,
                RoomSeat.GUEST: 0,
            }
            self.small_games_completed = 0
            self.taken_equipments.clear()
            self._reset_small_round_state_locked()
            self._clear_round_runtime_locked()
            self.round_deadline_ts = int((time.time() + self.round_seconds) * 1000)
            self.timeout_task = asyncio.create_task(self._schedule_round_timeout())

            room_message = {"action": "room_state", "state": self._serialize_room_state_locked()}
            battle_targets = self._build_battle_targets_locked("battle_state")
            room_targets = self._connected_targets_locked()

        await self._cancel_tasks(tasks)
        await self._broadcast_messages(room_targets, room_message)
        await self._broadcast_battle_messages(battle_targets)
        return True

    async def restart_match(self) -> None:
        async with self._lock:
            if not self.has_active_battle:
                return
            tasks = self._consume_round_tasks_locked()
            for player in self.players.values():
                player.equipments.clear()
                player.welfare.clear()
                player.charge_bonus = 0
            self.scores = {
                RoomSeat.HOST: 0,
                RoomSeat.GUEST: 0,
            }
            self.small_games_completed = 0
            self.taken_equipments.clear()
            self._reset_small_round_state_locked()
            self._clear_round_runtime_locked()
            self.round_deadline_ts = int((time.time() + self.round_seconds) * 1000)
            self.timeout_task = asyncio.create_task(self._schedule_round_timeout())
            battle_targets = self._build_battle_targets_locked("battle_state")
        await self._cancel_tasks(tasks)
        await self._broadcast_battle_messages(battle_targets)

    async def submit_card(self, seat: RoomSeat, card_id: str) -> None:
        timeout_task: asyncio.Task[Any] | None = None
        async with self._lock:
            if not self.has_active_battle:
                raise ValueError("battle has not started")
            if self.resolution:
                raise ValueError("current round has already resolved")
            if self.declared_actions[seat]:
                raise ValueError("you already played a card this round")

            battle_api = self._battle_api()
            chosen_action = battle_api.decode_action_id(card_id)
            actual_action = self._default_action_name() if self.round_index == 1 else chosen_action
            self.declared_actions[seat] = actual_action
            self.card_ready[seat] = True
            self.played_card_ids[seat] = battle_api.action_to_display_id(actual_action)

            battle_targets = self._build_battle_targets_locked("battle_state")
            should_resolve = (
                self.declared_actions[RoomSeat.HOST]
                and self.declared_actions[RoomSeat.GUEST]
                and not self.resolve_task
            )
            if should_resolve:
                self.resolve_task = asyncio.create_task(self._resolve_after_locked_preview())
                timeout_task = self._consume_timeout_task_locked()

        await self._broadcast_battle_messages(battle_targets)
        if timeout_task is not None and not timeout_task.done():
            timeout_task.cancel()

    def _connected_targets_locked(self, *, exclude: set[RoomSeat] | None = None) -> list[WebSocket]:
        exclude = exclude or set()
        targets: list[WebSocket] = []
        for seat, websocket in self._connections.items():
            if seat in exclude or websocket is None:
                continue
            targets.append(websocket)
        return targets

    def _build_battle_targets_locked(self, action: str) -> list[tuple[WebSocket, dict[str, Any]]]:
        targets: list[tuple[WebSocket, dict[str, Any]]] = []
        for seat, websocket in self._connections.items():
            if websocket is None:
                continue
            message: dict[str, Any] = {
                "action": action,
                "state": self._serialize_battle_state_for_locked(seat),
            }
            if action == "round_resolved" and self.resolution is not None:
                message["details"] = self._serialize_resolution_for_locked(seat)
            targets.append((websocket, message))
        return targets

    def _build_match_finished_targets_locked(self) -> list[tuple[WebSocket, dict[str, Any]]]:
        targets: list[tuple[WebSocket, dict[str, Any]]] = []
        host_score = self.scores[RoomSeat.HOST]
        guest_score = self.scores[RoomSeat.GUEST]
        overall_winner = "draw"
        if host_score > guest_score:
            overall_winner = RoomSeat.HOST.value
        elif guest_score > host_score:
            overall_winner = RoomSeat.GUEST.value

        for seat, websocket in self._connections.items():
            if websocket is None:
                continue
            other = self._other_seat(seat)
            winner = "draw"
            if overall_winner == seat.value:
                winner = "self"
            elif overall_winner == other.value:
                winner = "enemy"
            targets.append(
                (
                    websocket,
                    {
                        "action": "battle_finished",
                        "state": self._serialize_battle_state_for_locked(seat),
                        "details": {
                            "winner": winner,
                            "small_games_completed": self.small_games_completed,
                            "small_game_limit": self.small_game_limit,
                            "final_scores": {
                                "my": self.scores[seat],
                                "enemy": self.scores[other],
                            },
                        },
                    },
                )
            )
        return targets

    async def _schedule_round_timeout(self) -> None:
        try:
            deadline = self.round_deadline_ts
            if deadline is None:
                return
            remaining = max(0.0, deadline / 1000 - time.time())
            await asyncio.sleep(remaining)

            async with self._lock:
                if not self.has_active_battle or self.resolution:
                    return

                battle_api = self._battle_api()
                for seat in (RoomSeat.HOST, RoomSeat.GUEST):
                    if self.declared_actions[seat]:
                        continue
                    action_name = self._default_action_name()
                    self.declared_actions[seat] = action_name
                    self.card_ready[seat] = True
                    self.played_card_ids[seat] = battle_api.action_to_display_id(action_name)

                battle_targets = self._build_battle_targets_locked("battle_state")
                should_resolve = (
                    self.declared_actions[RoomSeat.HOST]
                    and self.declared_actions[RoomSeat.GUEST]
                    and not self.resolve_task
                )
                if should_resolve:
                    self.resolve_task = asyncio.create_task(self._resolve_after_locked_preview())
            await self._broadcast_battle_messages(battle_targets)
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                if asyncio.current_task() is self.timeout_task:
                    self.timeout_task = None

    async def _resolve_after_locked_preview(self) -> None:
        try:
            await asyncio.sleep(self.locked_card_preview_seconds)

            async with self._lock:
                if not self.has_active_battle or self.resolution:
                    return
                if not (self.declared_actions[RoomSeat.HOST] and self.declared_actions[RoomSeat.GUEST]):
                    return

                host_player = self.players[RoomSeat.HOST]
                guest_player = self.players[RoomSeat.GUEST]
                result = await asyncio.to_thread(
                    self.engine.resolve_round,
                    (host_player, guest_player),
                    {
                        host_player.player_id: self.declared_actions[RoomSeat.HOST],
                        guest_player.player_id: self.declared_actions[RoomSeat.GUEST],
                    },
                    first_round_of_small_game=self.round_index == 1,
                )

                battle_api = self._battle_api()
                self.played_card_ids[RoomSeat.HOST] = battle_api.action_to_display_id(
                    result.actions[host_player.player_id]
                )
                self.played_card_ids[RoomSeat.GUEST] = battle_api.action_to_display_id(
                    result.actions[guest_player.player_id]
                )
                self.reveal_cards = True
                self.resolution = self._build_resolution_locked(result)
                if self._small_game_finished_locked():
                    self.small_games_completed += 1
                self.resolution["small_games_completed"] = self.small_games_completed
                self.resolution["small_game_limit"] = self.small_game_limit
                self.resolution["match_finished"] = self.small_games_completed >= self.small_game_limit
                battle_targets = self._build_battle_targets_locked("round_resolved")
                self.advance_task = asyncio.create_task(self._auto_advance_after_reveal())
            await self._broadcast_battle_messages(battle_targets)
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                if asyncio.current_task() is self.resolve_task:
                    self.resolve_task = None

    async def _auto_advance_after_reveal(self) -> None:
        try:
            await asyncio.sleep(self.reveal_delay_seconds)

            close_targets: list[WebSocket] = []
            room_targets: list[WebSocket] = []
            room_message: dict[str, Any] | None = None
            battle_targets: list[tuple[WebSocket, dict[str, Any]]] = []
            finished_targets: list[tuple[WebSocket, dict[str, Any]]] = []
            should_close_match = False

            async with self._lock:
                if not self.has_active_battle:
                    return

                if self.resolution and self.resolution.get("match_finished"):
                    self._state = await self.service.set_room_status(self.room_code, RoomStatus.FINISHED)
                    room_message = {"action": "room_state", "state": self._serialize_room_state_locked()}
                    finished_targets = self._build_match_finished_targets_locked()
                    close_targets = self._connected_targets_locked()
                    room_targets = list(close_targets)
                    self._connections = {RoomSeat.HOST: None, RoomSeat.GUEST: None}
                    self.engine = None
                    self.players = {}
                    self._clear_round_runtime_locked()
                    should_close_match = True
                else:
                    winner = self.resolution.get("winner_seat") if self.resolution else None
                    if winner in {RoomSeat.HOST.value, RoomSeat.GUEST.value, "draw"}:
                        self._reset_small_round_state_locked()
                    else:
                        self.round_index += 1

                    self._clear_round_runtime_locked()
                    self.round_deadline_ts = int((time.time() + self.round_seconds) * 1000)
                    self.timeout_task = asyncio.create_task(self._schedule_round_timeout())
                    battle_targets = self._build_battle_targets_locked("battle_state")

            if should_close_match:
                if room_message is not None:
                    await self._broadcast_messages(room_targets, room_message)
                await self._broadcast_battle_messages(finished_targets)
                await self._broadcast_messages(
                    close_targets,
                    {"action": "room_closed", "payload": {"reason": "match_finished"}},
                )
                await self._close_websockets(close_targets)
                await self.service.close_room(self.room_code)
                await self._notify_manager_closed()
            else:
                await self._broadcast_battle_messages(battle_targets)
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                if asyncio.current_task() is self.advance_task:
                    self.advance_task = None

    def _build_resolution_locked(self, result: RoundResult) -> dict[str, Any]:
        host_player = self.players[RoomSeat.HOST]
        guest_player = self.players[RoomSeat.GUEST]
        host_action = result.actions.get(host_player.player_id, "")
        guest_action = result.actions.get(guest_player.player_id, "")
        host_status = "dead" if not host_player.alive else "normal"
        guest_status = "dead" if not guest_player.alive else "normal"

        resolution: dict[str, Any] = {
            "card_status": {
                RoomSeat.HOST.value: "crushed"
                if host_action in result.smashed_this_round.get(host_player.player_id, set())
                else "normal",
                RoomSeat.GUEST.value: "crushed"
                if guest_action in result.smashed_this_round.get(guest_player.player_id, set())
                else "normal",
            },
            "player_status": {
                RoomSeat.HOST.value: host_status,
                RoomSeat.GUEST.value: guest_status,
            },
            "winner_seat": None,
            "granted_equipment": None,
            "granted_equipment_seat": None,
            "logs": result.logs,
        }

        if result.draw_restart:
            resolution["winner_seat"] = "draw"
            return resolution

        if result.dead_players:
            if host_player.alive and not guest_player.alive:
                resolution["winner_seat"] = RoomSeat.HOST.value
                self.scores[RoomSeat.HOST] += 1
                granted = self.engine.grant_next_equipment(host_player, self.taken_equipments)
                if granted:
                    self.taken_equipments.add(granted)
                    resolution["granted_equipment"] = granted
                    resolution["granted_equipment_seat"] = RoomSeat.HOST.value
            elif guest_player.alive and not host_player.alive:
                resolution["winner_seat"] = RoomSeat.GUEST.value
                self.scores[RoomSeat.GUEST] += 1
                granted = self.engine.grant_next_equipment(guest_player, self.taken_equipments)
                if granted:
                    self.taken_equipments.add(granted)
                    resolution["granted_equipment"] = granted
                    resolution["granted_equipment_seat"] = RoomSeat.GUEST.value

        return resolution

    def _small_game_finished_locked(self) -> bool:
        if self.resolution is None:
            return False
        return self.resolution.get("winner_seat") in {
            RoomSeat.HOST.value,
            RoomSeat.GUEST.value,
            "draw",
        }

    def _serialize_resolution_for_locked(self, viewer_seat: RoomSeat) -> dict[str, Any] | None:
        if self.resolution is None:
            return None
        other = self._other_seat(viewer_seat)
        winner_seat = self.resolution.get("winner_seat")
        winner = None
        if winner_seat == "draw":
            winner = "draw"
        elif winner_seat == viewer_seat.value:
            winner = "self"
        elif winner_seat == other.value:
            winner = "enemy"
        payload = {
            "my_card_status": self.resolution["card_status"][viewer_seat.value],
            "enemy_card_status": self.resolution["card_status"][other.value],
            "my_status": self.resolution["player_status"][viewer_seat.value],
            "enemy_status": self.resolution["player_status"][other.value],
            "winner": winner,
            "logs": self.resolution["logs"],
            "small_games_completed": self.resolution.get("small_games_completed", self.small_games_completed),
            "small_game_limit": self.resolution.get("small_game_limit", self.small_game_limit),
            "match_finished": self.resolution.get(
                "match_finished",
                self.small_games_completed >= self.small_game_limit,
            ),
        }
        if self.resolution.get("granted_equipment"):
            payload["granted_equipment"] = self.resolution["granted_equipment"]
        return payload

    def _serialize_equipment_state_locked(self, player: PlayerState) -> list[dict[str, Any]]:
        battle_api = self._battle_api()
        items: list[dict[str, Any]] = []
        for equipment_name, state in player.equipments.items():
            summary = battle_api.summarize_equipment(equipment_name, state)
            items.append(
                {
                    "id": battle_api.NAME_TO_EQUIPMENT_ID.get(equipment_name, equipment_name),
                    "name": summary["label"],
                    "phase": summary["phase"],
                    "theme": battle_api.build_equipment_theme(equipment_name),
                }
            )
        return items

    def _serialize_player_state_locked(self, seat: RoomSeat) -> dict[str, Any]:
        battle_api = self._battle_api()
        player = self.players[seat]
        status = "dead" if not player.alive else "normal"
        if player.alive and player.statuses:
            status = "/".join(sorted(player.statuses))
        return {
            "energy": battle_api.serialize_energy(player.energy),
            "equipment": self._serialize_equipment_state_locked(player),
            "status": status,
            "hp": 1 if player.alive else 0,
            "statuses": sorted(player.statuses),
            "score": self.scores[seat],
        }

    def _build_hand_ids_locked(self, seat: RoomSeat) -> list[str]:
        battle_api = self._battle_api()
        player = self.players[seat]
        hand_ids: list[str] = []
        for name, skill in self.engine.available_skills(player).items():
            can_afford = False
            if skill.alt_cost:
                for counter_name, need in skill.alt_cost.items():
                    if player.counters.get(counter_name, 0) >= need:
                        can_afford = True
                        break
            if can_afford or float(player.energy) >= float(skill.energy_cost):
                hand_ids.append(battle_api.encode_skill_id(name))

        for equipment_name in self.engine.super_rate_candidates(player):
            if float(player.energy) >= 3.0:
                hand_ids.append(battle_api.encode_super_rate_id(equipment_name))

        if self.declared_actions[seat] and not self.reveal_cards:
            played_id = battle_api.action_to_display_id(self.declared_actions[seat])
            if played_id in hand_ids:
                hand_ids.remove(played_id)
        return hand_ids

    def _build_card_catalog_locked(self, card_ids: list[str]) -> dict[str, Any]:
        battle_api = self._battle_api()
        catalog: dict[str, Any] = {}
        for card_id in card_ids:
            if card_id:
                catalog[card_id] = battle_api.build_card_meta_from_action_id(card_id)
        return catalog

    def _serialize_battle_state_for_locked(self, viewer_seat: RoomSeat) -> dict[str, Any]:
        other = self._other_seat(viewer_seat)
        hand_ids = self._build_hand_ids_locked(viewer_seat)
        visible_cards = [
            card_id
            for card_id in (
                self.played_card_ids[viewer_seat],
                self.played_card_ids[other],
            )
            if card_id
        ]
        return {
            "round": self.round_index,
            "my_state": self._serialize_player_state_locked(viewer_seat),
            "enemy_state": self._serialize_player_state_locked(other),
            "hand_cards": hand_ids,
            "battlefield": {
                "my_card_played": self.played_card_ids[viewer_seat],
                "enemy_card_played": self.played_card_ids[other],
                "my_card_ready": self.card_ready[viewer_seat],
                "enemy_card_ready": self.card_ready[other],
                "reveal_cards": self.reveal_cards,
                "resolution": self._serialize_resolution_for_locked(viewer_seat),
            },
            "timer": {
                "round_seconds": self.round_seconds,
                "deadline_ts": self.round_deadline_ts,
            },
            "card_catalog": self._build_card_catalog_locked(hand_ids + visible_cards),
            "scores": {
                "my": self.scores[viewer_seat],
                "enemy": self.scores[other],
            },
            "match": {
                "small_games_completed": self.small_games_completed,
                "small_game_limit": self.small_game_limit,
                "finished": self.small_games_completed >= self.small_game_limit,
            },
        }

    async def _broadcast_messages(self, targets: list[WebSocket], message: dict[str, Any]) -> None:
        for websocket in list(targets):
            await self._safe_send_json(websocket, message)

    async def _broadcast_battle_messages(self, targets: list[tuple[WebSocket, dict[str, Any]]]) -> None:
        for websocket, message in list(targets):
            await self._safe_send_json(websocket, message)

    async def _safe_send_json(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            return

    async def _close_websockets(self, targets: list[WebSocket]) -> None:
        for websocket in list(targets):
            with contextlib.suppress(Exception):
                await websocket.close()
