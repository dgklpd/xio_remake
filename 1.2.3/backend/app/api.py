from __future__ import annotations

import asyncio
import contextlib
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..agents import PlayerAgent, build_agent
from ..core.rules import (
    EQUIPMENT_BLUEPRINTS,
    SKILLS,
    EquipmentState,
    F,
    PlayerState,
    RoundResult,
    RuleEngine,
    Skill,
    create_players,
    format_energy,
)
from ..online import (
    AuthProvider,
    InvalidRoomCodeError,
    OnlineRoomError,
    OnlineRoomService,
    PlayerIdentity,
    RoomClosedError,
    RoomExpiredError,
    RoomFullError,
    RoomManager,
    RoomNotFoundError,
    RoomSeat,
    RoomStateView,
    RoomStatus,
)

ROUND_SECONDS = 10
LOCKED_CARD_PREVIEW_SECONDS = 0.45
REVEAL_DELAY_SECONDS = 2.2

CARD_ID_TO_NAME = {
    "xu": "蓄",
    "di_bo": "地波",
    "tian_bo": "天波",
    "bo_bo": "波波",
    "lei_ba": "雷八",
    "chao_fang": "超防",
    "san_kan": "三砍",
    "wu_he_ti": "五合体",
    "hu_he_ti": "虎合体",
    "chao_lv": "超率",
    "tian_ma": "天马",
    "tian_ma_liu_xing_quan": "天马流星拳",
    "tian_ma_hui_xing_quan": "天马彗星拳",
    "tian_ma_hou_kong_fan": "天马后空翻",
    "bing_dun": "冰盾",
    "bao_bing": "爆冰",
    "bao_bing_quan": "爆冰拳",
    "ning_bing": "凝冰",
    "jing_bing_quan": "晶冰拳",
    "long_dun": "龙盾",
    "bao_long": "爆龙",
    "bao_long_quan": "爆龙拳",
    "jin_long_quan": "金龙拳",
    "mian_yi": "免疫",
    "xiao_mian": "小免",
    "da_mian": "大免",
    "nuo_yi": "挪移",
    "zheng_yi": "正义",
    "fan_she_jing": "反射镜",
    "chuan_xin_jing": "穿心镜",
    "ka_zi_quan": "卡兹拳",
    "ka_zi_guang": "卡兹光",
    "ka_zi_mo": "卡兹膜",
    "niu_dun": "牛盾",
    "ding": "顶",
    "lang_quan": "狼拳",
    "bing_lang_quan": "冰狼拳",
    "jin_lang_quan": "金狼拳",
    "xiao_dun": "小盾",
}
NAME_TO_CARD_ID = {value: key for key, value in CARD_ID_TO_NAME.items()}

EQUIPMENT_ID_TO_NAME = {
    "tian_ma": "天马",
    "bing_dun": "冰盾",
    "long_dun": "龙盾",
    "mian_yi": "免疫",
    "zheng_yi": "正义",
    "niu_bo": "牛脖",
    "lang_quan": "狼拳",
}
NAME_TO_EQUIPMENT_ID = {value: key for key, value in EQUIPMENT_ID_TO_NAME.items()}

SKILL_TO_EQUIPMENT: dict[str, str] = {}
for equipment_name, blueprint in EQUIPMENT_BLUEPRINTS.items():
    for skill_names in blueprint.phase_skills.values():
        for skill_name in skill_names:
            SKILL_TO_EQUIPMENT.setdefault(skill_name, equipment_name)
    for combo_rule in blueprint.combo_rules:
        SKILL_TO_EQUIPMENT.setdefault(combo_rule.skill_name, equipment_name)


def serialize_energy(value: Any) -> int | float:
    if getattr(value, "denominator", 1) == 1:
        return int(value)
    return float(value)


def encode_skill_id(skill_name: str) -> str:
    return NAME_TO_CARD_ID.get(skill_name, skill_name)


def encode_super_rate_id(equipment_name: str) -> str:
    equipment_id = NAME_TO_EQUIPMENT_ID.get(equipment_name, equipment_name)
    return f"super_rate__{equipment_id}"


def decode_action_id(card_id: str) -> str:
    if card_id.startswith("super_rate__"):
        equipment_id = card_id.split("__", 1)[1]
        equipment_name = EQUIPMENT_ID_TO_NAME.get(equipment_id)
        if not equipment_name:
            raise ValueError(f"未知超率目标：{equipment_id}")
        return f"超率:{equipment_name}"

    if card_id not in CARD_ID_TO_NAME:
        raise ValueError(f"未知卡牌：{card_id}")

    return CARD_ID_TO_NAME[card_id]


def action_to_display_id(action_name: str) -> str:
    if action_name.startswith("超率:"):
        _, _, equipment_name = action_name.partition(":")
        return encode_super_rate_id(equipment_name)
    return encode_skill_id(action_name)


def build_skill_keywords(skill: Skill) -> list[str]:
    keywords: list[str] = []

    if skill.deteriorate_ground:
        keywords.append("对地劣化")
    if skill.deteriorate_air:
        keywords.append("对空劣化")
    if skill.alt_cost:
        keywords.append("替代消耗")

    special_map = {
        "charge": "能量增长",
        "fly": "飞天",
        "dive": "遁地",
        "super_rate": "升级",
        "lei_ba": "点杀",
        "smash_mian_yi": "破免",
        "smash_shield": "破盾",
        "smash_strong_attack": "强拆",
        "smash_weak_attack": "碎弱攻",
        "reflect_lt3": "反射",
        "reflect_le45": "强反射",
    }
    for special in skill.specials:
        label = special_map.get(special)
        if label and label not in keywords:
            keywords.append(label)

    for tag in sorted(skill.tags):
        if tag == "mian_yi":
            keywords.append("免疫")
        elif tag == "ning_bing":
            keywords.append("凝冰")

    return keywords[:3]


def build_skill_theme(skill_name: str, skill: Skill) -> str:
    if skill_name in {"蓄", "超率", "五合体", "虎合体"}:
        return "gold"
    if skill_name in {"雷八", "天马", "天马流星拳", "天马彗星拳"}:
        return "storm"
    if skill.category == "defense":
        return "paper"
    if skill.energy_cost >= F(3):
        return "crimson"
    return "azure"


def build_skill_kind(skill_name: str, skill: Skill) -> str:
    if skill_name == "蓄":
        return "蓄"
    if skill.category == "attack":
        return "攻"
    if skill.category == "defense":
        return "守"
    return "技"


def build_skill_subtitle(skill_name: str) -> str:
    equipment_name = SKILL_TO_EQUIPMENT.get(skill_name)
    if equipment_name:
        return equipment_name
    if skill_name in {"蓄", "地波", "天波", "波波", "雷八", "超防", "三砍", "五合体", "虎合体"}:
        return "基础局"
    return "技能"


def build_card_meta_from_action_id(card_id: str) -> dict[str, Any]:
    if card_id.startswith("super_rate__"):
        equipment_id = card_id.split("__", 1)[1]
        equipment_name = EQUIPMENT_ID_TO_NAME.get(equipment_id, equipment_id)
        return {
            "name": "超率",
            "kind": "技",
            "subtitle": equipment_name,
            "cost_label": "3",
            "attack_label": "-",
            "defense_label": "∞",
            "special_text": f"消耗 3 点蓄能量，升级 {equipment_name} 的下一阶段。",
            "keywords": ["升级", equipment_name],
            "theme": "gold",
        }

    skill_name = CARD_ID_TO_NAME.get(card_id, card_id)
    skill = SKILLS[skill_name]
    attack_label = format_energy(skill.attack) if skill.attack > 0 else "-"
    defense_label = format_energy(skill.defense) if skill.defense > 0 else "0"
    return {
        "name": skill_name,
        "kind": build_skill_kind(skill_name, skill),
        "subtitle": build_skill_subtitle(skill_name),
        "cost_label": format_energy(skill.energy_cost),
        "attack_label": attack_label,
        "defense_label": defense_label,
        "special_text": skill.desc or "以服务端判定结果为准。",
        "keywords": build_skill_keywords(skill),
        "theme": build_skill_theme(skill_name, skill),
    }


def build_equipment_theme(equipment_name: str) -> str:
    if equipment_name in {"冰盾", "龙盾"}:
        return "frost"
    if equipment_name in {"狼拳", "牛脖"}:
        return "jade"
    return "solar"


def summarize_equipment(equipment_name: str, state: EquipmentState) -> dict[str, str]:
    phase_text = f"{state.phase}"
    if equipment_name == "狼拳":
        phase_text = "连携"
    return {
        "phase": phase_text,
        "label": equipment_name,
    }


@dataclass
class SinglePlayerBattleSession:
    engine: RuleEngine
    human: PlayerState
    enemy: PlayerState
    ai_agent: PlayerAgent
    scores: dict[int, int]
    taken_equipments: set[str]
    round_index: int = 1
    round_deadline_ts: int | None = None
    round_seconds: int = ROUND_SECONDS
    my_declared_action: str | None = None
    enemy_declared_action: str | None = None
    my_card_played: str | None = None
    enemy_card_played: str | None = None
    my_card_ready: bool = False
    enemy_card_ready: bool = False
    reveal_cards: bool = False
    resolution: dict[str, Any] | None = None
    event_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    enemy_task: asyncio.Task[None] | None = None
    timeout_task: asyncio.Task[None] | None = None
    resolve_task: asyncio.Task[None] | None = None
    advance_task: asyncio.Task[None] | None = None
    closed: bool = False

    @classmethod
    async def create(
        cls,
        *,
        ai_kind: str = "rl",
        ai_name: str = "AI",
        rl_model_path: str | None = None,
        deterministic: bool = False,
        think_time: float = 0.0,
    ) -> "SinglePlayerBattleSession":
        players = create_players(2)
        session = cls(
            engine=RuleEngine(),
            human=players[0],
            enemy=players[1],
            ai_agent=build_agent(
                ai_kind,
                ai_name,
                rl_model_path=rl_model_path,
                deterministic=deterministic,
                think_time=think_time,
            ),
            scores={1: 0, 2: 0},
            taken_equipments=set(),
        )
        session.reset_small_round_state()
        await session.start_round(push_event=True)
        return session

    async def close(self) -> None:
        self.closed = True
        await self._cancel_round_tasks()

    async def _cancel_round_tasks(self) -> None:
        for task in (
            self.enemy_task,
            self.timeout_task,
            self.resolve_task,
            self.advance_task,
        ):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self.enemy_task = None
        self.timeout_task = None
        self.resolve_task = None
        self.advance_task = None

    async def emit(self, payload: dict[str, Any]) -> None:
        if not self.closed:
            await self.event_queue.put(payload)

    async def emit_state(self, action: str = "game_state") -> None:
        await self.emit({"action": action, "state": self.serialize_state()})

    async def next_event(self) -> dict[str, Any]:
        return await self.event_queue.get()

    def reset_small_round_state(self) -> None:
        for player in (self.human, self.enemy):
            player.small_round_reset()
        self.engine.apply_welfare_if_needed((self.human, self.enemy))
        self.round_index = 1

    async def restart_match(self) -> None:
        for player in (self.human, self.enemy):
            player.equipments.clear()
            player.welfare.clear()
            player.charge_bonus = 0
        self.scores = {1: 0, 2: 0}
        self.taken_equipments.clear()
        self.reset_small_round_state()
        await self.start_round(push_event=True)

    async def start_round(self, push_event: bool = True) -> None:
        await self._cancel_round_tasks()
        self.round_deadline_ts = int((time.time() + self.round_seconds) * 1000)
        self.my_declared_action = None
        self.enemy_declared_action = None
        self.my_card_played = None
        self.enemy_card_played = None
        self.my_card_ready = False
        self.enemy_card_ready = False
        self.reveal_cards = False
        self.resolution = None

        self.enemy_task = asyncio.create_task(self._schedule_enemy_action())
        self.timeout_task = asyncio.create_task(self._schedule_round_timeout())

        if push_event:
            await self.emit_state("game_state")

    async def _schedule_enemy_action(self) -> None:
        try:
            if self.closed or self.enemy_declared_action or self.resolution:
                return

            is_first_round = self.round_index == 1
            action = await asyncio.to_thread(
                self.ai_agent.get_action,
                self.engine,
                self.enemy,
                [self.human],
                is_first_round,
            )
            self.enemy_declared_action = "蓄" if is_first_round else action
            self.enemy_card_ready = True
            self.enemy_card_played = action_to_display_id(self.enemy_declared_action)
            await self.emit_state("game_state")
            await self.resolve_if_ready()
        except asyncio.CancelledError:
            raise

    async def _schedule_round_timeout(self) -> None:
        try:
            remaining = max(0, (self.round_deadline_ts or 0) / 1000 - time.time())
            await asyncio.sleep(remaining)
            if self.closed or self.resolution:
                return

            if not self.my_declared_action:
                self.my_declared_action = "蓄"
                self.my_card_ready = True
                self.my_card_played = action_to_display_id(self.my_declared_action)
            if not self.enemy_declared_action:
                self.enemy_declared_action = "蓄"
                self.enemy_card_ready = True
                self.enemy_card_played = action_to_display_id(self.enemy_declared_action)

            await self.emit_state("game_state")
            await self.resolve_if_ready()
        except asyncio.CancelledError:
            raise

    async def submit_human_card(self, card_id: str) -> None:
        if self.closed:
            return
        if self.resolution:
            raise ValueError("当前回合已经结算，请等待下一回合。")
        if self.my_declared_action:
            raise ValueError("本回合你已经出过牌了。")

        chosen_action = decode_action_id(card_id)
        actual_action = "蓄" if self.round_index == 1 else chosen_action
        self.my_declared_action = actual_action
        self.my_card_ready = True
        self.my_card_played = action_to_display_id(actual_action)
        await self.emit_state("game_state")
        await self.resolve_if_ready()

    async def resolve_if_ready(self) -> None:
        if self.resolution or not (self.my_declared_action and self.enemy_declared_action):
            return

        current_task = asyncio.current_task()

        if self.enemy_task and not self.enemy_task.done() and self.enemy_task is not current_task:
            self.enemy_task.cancel()
        if self.timeout_task and not self.timeout_task.done() and self.timeout_task is not current_task:
            self.timeout_task.cancel()

        if self.resolve_task and not self.resolve_task.done():
            return

        self.resolve_task = asyncio.create_task(self._resolve_after_locked_preview())

    async def _resolve_after_locked_preview(self) -> None:
        try:
            await asyncio.sleep(LOCKED_CARD_PREVIEW_SECONDS)
            if self.closed or self.resolution:
                return
            if not (self.my_declared_action and self.enemy_declared_action):
                return

            result = await asyncio.to_thread(
                self.engine.resolve_round,
                (self.human, self.enemy),
                {
                    self.human.player_id: self.my_declared_action,
                    self.enemy.player_id: self.enemy_declared_action,
                },
                first_round_of_small_game=self.round_index == 1,
            )
            self.ai_agent.on_round_resolved(result.actions)

            self.my_card_played = action_to_display_id(result.actions[self.human.player_id])
            self.enemy_card_played = action_to_display_id(result.actions[self.enemy.player_id])
            self.reveal_cards = True
            self.resolution = self.build_resolution(result)

            await self.emit(
                {
                    "action": "round_resolved",
                    "state": self.serialize_state(),
                    "details": self.resolution,
                }
            )
            self.advance_task = asyncio.create_task(self._auto_advance_after_reveal())
        except asyncio.CancelledError:
            raise
        finally:
            self.resolve_task = None

    async def _auto_advance_after_reveal(self) -> None:
        try:
            await asyncio.sleep(REVEAL_DELAY_SECONDS)
            if self.closed:
                return

            if self.resolution and self.resolution.get("winner") in {"self", "enemy", "draw"}:
                self.reset_small_round_state()
            else:
                self.round_index += 1

            await self.start_round(push_event=True)
        except asyncio.CancelledError:
            raise

    def build_resolution(self, result: RoundResult) -> dict[str, Any]:
        my_action = result.actions.get(self.human.player_id, "")
        enemy_action = result.actions.get(self.enemy.player_id, "")
        my_status = "dead" if not self.human.alive else "normal"
        enemy_status = "dead" if not self.enemy.alive else "normal"

        resolution: dict[str, Any] = {
            "my_card_status": "crushed"
            if my_action in result.smashed_this_round.get(self.human.player_id, set())
            else "normal",
            "enemy_card_status": "crushed"
            if enemy_action in result.smashed_this_round.get(self.enemy.player_id, set())
            else "normal",
            "my_status": my_status,
            "enemy_status": enemy_status,
            "winner": None,
            "logs": result.logs,
        }

        if result.draw_restart:
            resolution["winner"] = "draw"
            return resolution

        if result.dead_players:
            if self.human.alive and not self.enemy.alive:
                resolution["winner"] = "self"
                self.scores[self.human.player_id] += 1
                granted = self.engine.grant_next_equipment(self.human, self.taken_equipments)
                if granted:
                    self.taken_equipments.add(granted)
                    resolution["granted_equipment"] = granted
            elif self.enemy.alive and not self.human.alive:
                resolution["winner"] = "enemy"
                self.scores[self.enemy.player_id] += 1
                granted = self.engine.grant_next_equipment(self.enemy, self.taken_equipments)
                if granted:
                    self.taken_equipments.add(granted)
                    resolution["granted_equipment"] = granted

        return resolution

    def serialize_equipment_state(self, player: PlayerState) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for equipment_name, state in player.equipments.items():
            summary = summarize_equipment(equipment_name, state)
            items.append(
                {
                    "id": NAME_TO_EQUIPMENT_ID.get(equipment_name, equipment_name),
                    "name": summary["label"],
                    "phase": summary["phase"],
                    "theme": build_equipment_theme(equipment_name),
                }
            )
        return items

    def serialize_player_state(self, player: PlayerState) -> dict[str, Any]:
        status = "dead" if not player.alive else "normal"
        if player.alive and player.statuses:
            status = "/".join(sorted(player.statuses))
        return {
            "energy": serialize_energy(player.energy),
            "equipment": self.serialize_equipment_state(player),
            "status": status,
            "hp": 1 if player.alive else 0,
            "statuses": sorted(player.statuses),
            "score": self.scores[player.player_id],
        }

    def build_hand_ids(self) -> list[str]:
        hand_ids = []
        for name, skill in self.engine.available_skills(self.human).items():
            can_afford = False
            if skill.alt_cost:
                for counter_name, need in skill.alt_cost.items():
                    if self.human.counters.get(counter_name, 0) >= need:
                        can_afford = True
                        break
            if can_afford or float(self.human.energy) >= float(skill.energy_cost):
                hand_ids.append(encode_skill_id(name))

        for equipment_name in self.engine.super_rate_candidates(self.human):
            if float(self.human.energy) >= 3.0:
                hand_ids.append(encode_super_rate_id(equipment_name))

        if self.my_declared_action and not self.reveal_cards:
            played_id = action_to_display_id(self.my_declared_action)
            if played_id in hand_ids:
                hand_ids.remove(played_id)
        return hand_ids

    def build_card_catalog(self, card_ids: list[str]) -> dict[str, Any]:
        catalog: dict[str, Any] = {}
        for card_id in card_ids:
            if card_id:
                catalog[card_id] = build_card_meta_from_action_id(card_id)
        return catalog

    def serialize_state(self) -> dict[str, Any]:
        hand_ids = self.build_hand_ids()
        visible_cards = [
            card_id for card_id in (self.my_card_played, self.enemy_card_played) if card_id
        ]
        return {
            "round": self.round_index,
            "my_state": self.serialize_player_state(self.human),
            "enemy_state": self.serialize_player_state(self.enemy),
            "hand_cards": hand_ids,
            "battlefield": {
                "my_card_played": self.my_card_played,
                "enemy_card_played": self.enemy_card_played,
                "my_card_ready": self.my_card_ready,
                "enemy_card_ready": self.enemy_card_ready,
                "reveal_cards": self.reveal_cards,
                "resolution": self.resolution,
            },
            "timer": {
                "round_seconds": self.round_seconds,
                "deadline_ts": self.round_deadline_ts,
            },
            "card_catalog": self.build_card_catalog(hand_ids + visible_cards),
            "scores": {
                "my": self.scores[self.human.player_id],
                "enemy": self.scores[self.enemy.player_id],
            },
        }


class OnlineIdentityPayload(BaseModel):
    display_name: str = "玩家"
    avatar_url: str = ""
    auth_provider: AuthProvider = AuthProvider.GUEST
    external_user_id: str | None = None
    is_guest: bool = True


class CreateRoomRequest(BaseModel):
    identity: OnlineIdentityPayload | None = None
    room_name: str | None = None


class JoinRoomRequest(BaseModel):
    identity: OnlineIdentityPayload | None = None


class ReadyRoomRequest(BaseModel):
    seat: RoomSeat
    ready: bool = True


class LeaveRoomRequest(BaseModel):
    seat: RoomSeat


def online_identity_from_payload(payload: OnlineIdentityPayload | None) -> PlayerIdentity | None:
    if payload is None:
        return None
    return PlayerIdentity(
        display_name=payload.display_name,
        avatar_url=payload.avatar_url,
        auth_provider=payload.auth_provider,
        external_user_id=payload.external_user_id,
        is_guest=payload.is_guest,
    )


def serialize_online_seat(seat: Any) -> dict[str, Any] | None:
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


def serialize_online_room_state(room: RoomStateView) -> dict[str, Any]:
    guest = room.guest
    can_start = bool(
        guest
        and room.host.ready
        and guest.ready
        and room.status in {RoomStatus.WAITING, RoomStatus.FULL}
    )
    return {
        "room_code": room.room_code,
        "room_name": room.room_name,
        "status": room.status.value,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
        "expires_at": room.expires_at,
        "host": serialize_online_seat(room.host),
        "guest": serialize_online_seat(guest),
        "can_start": can_start,
    }


def serialize_online_room_list_item(item: Any) -> dict[str, Any]:
    return {
        "room_code": item.room_code,
        "room_name": item.room_name,
        "status": item.status.value,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "expires_at": item.expires_at,
        "host_display_name": item.host_display_name,
        "guest_display_name": item.guest_display_name,
        "host_connected": item.host_connected,
        "guest_connected": item.guest_connected,
        "host_ready": item.host_ready,
        "guest_ready": item.guest_ready,
    }


def online_error_to_http(exc: OnlineRoomError) -> HTTPException:
    if isinstance(exc, InvalidRoomCodeError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RoomNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RoomFullError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RoomClosedError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RoomExpiredError):
        return HTTPException(status_code=410, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


app = FastAPI(title="Xu Single Player API")
online_room_manager = RoomManager(OnlineRoomService())


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.on_event("startup")
async def initialize_online_rooms() -> None:
    await online_room_manager.initialize()


@app.post("/online/rooms")
async def create_online_room(request: CreateRoomRequest) -> dict[str, Any]:
    try:
        result = await online_room_manager.create_room(
            online_identity_from_payload(request.identity),
            room_name=request.room_name,
        )
    except OnlineRoomError as exc:
        raise online_error_to_http(exc) from exc
    return {
        "seat": result.seat.value,
        "session_token": result.session_token,
        "room": serialize_online_room_state(result.room),
    }


@app.get("/online/rooms")
async def list_online_rooms(limit: int = 60) -> dict[str, Any]:
    rooms = await online_room_manager.service.list_rooms(limit=max(1, min(limit, 100)))
    return {"rooms": [serialize_online_room_list_item(item) for item in rooms]}


@app.post("/online/rooms/{room_code}/join")
async def join_online_room(room_code: str, request: JoinRoomRequest) -> dict[str, Any]:
    try:
        result = await online_room_manager.join_room(
            room_code,
            online_identity_from_payload(request.identity),
        )
    except OnlineRoomError as exc:
        raise online_error_to_http(exc) from exc
    return {
        "seat": result.seat.value,
        "session_token": result.session_token,
        "room": serialize_online_room_state(result.room),
    }


@app.get("/online/rooms/{room_code}")
async def get_online_room(room_code: str) -> dict[str, Any]:
    try:
        room = await online_room_manager.get_room_state(room_code)
    except OnlineRoomError as exc:
        raise online_error_to_http(exc) from exc
    return {"room": serialize_online_room_state(room)}


@app.post("/online/rooms/{room_code}/ready")
async def ready_online_room(room_code: str, request: ReadyRoomRequest) -> dict[str, Any]:
    try:
        room = await online_room_manager.set_ready(room_code, request.seat, request.ready)
    except OnlineRoomError as exc:
        raise online_error_to_http(exc) from exc
    return {"room": serialize_online_room_state(room)}


@app.post("/online/rooms/{room_code}/leave")
async def leave_online_room(room_code: str, request: LeaveRoomRequest) -> dict[str, Any]:
    try:
        room = await online_room_manager.leave_room(room_code, request.seat)
    except OnlineRoomError as exc:
        raise online_error_to_http(exc) from exc
    if room is None:
        return {"closed": True, "room": None}
    return {"closed": False, "room": serialize_online_room_state(room)}


@app.websocket("/ws/online/rooms/{room_code}")
async def online_room_socket(
    websocket: WebSocket,
    room_code: str,
    seat: RoomSeat,
    session_token: str,
) -> None:
    await websocket.accept()
    session = None
    registered = False

    try:
        session = await online_room_manager.get_session(room_code)
        await session.register_connection(seat, session_token, websocket)
        registered = True

        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            payload = message.get("payload") or {}

            if action == "ping":
                await websocket.send_json({"action": "pong"})
                continue

            if action == "ready_room":
                ready = bool(payload.get("ready", True))
                await session.set_ready(seat, ready)
                if ready:
                    await session.start_battle_if_ready()
                continue

            if action == "play_card":
                card_id = str(payload.get("card_id", "")).strip()
                try:
                    await session.submit_card(seat, card_id)
                except ValueError as exc:
                    await websocket.send_json(
                        {
                            "action": "error",
                            "payload": {"message": str(exc)},
                        }
                    )
                continue

            if action == "restart_match":
                await session.restart_match()
                continue

            if action == "get_room_state":
                room = await online_room_manager.get_room_state(room_code)
                await websocket.send_json(
                    {
                        "action": "room_state",
                        "state": serialize_online_room_state(room),
                    }
                )
                continue

            await websocket.send_json(
                {
                    "action": "error",
                    "payload": {"message": f"unknown action: {action}"},
                }
            )
    except PermissionError:
        await websocket.send_json(
            {
                "action": "error",
                "payload": {"message": "invalid session token"},
            }
        )
        await websocket.close(code=1008)
    except OnlineRoomError as exc:
        await websocket.send_json(
            {
                "action": "error",
                "payload": {"message": str(exc)},
            }
        )
        await websocket.close(code=1011)
    except WebSocketDisconnect:
        pass
    finally:
        if registered and session is not None:
            await session.unregister_connection(seat, websocket)


async def socket_sender(websocket: WebSocket, session: SinglePlayerBattleSession) -> None:
    while True:
        message = await session.next_event()
        await websocket.send_json(message)


@app.websocket("/ws/battle")
async def battle_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    session = await SinglePlayerBattleSession.create(
        ai_kind=os.getenv("BACKEND_BATTLE_AI", "rl"),
        ai_name=os.getenv("BACKEND_BATTLE_AI_NAME", "AI"),
        rl_model_path=os.getenv("BACKEND_BATTLE_RL_MODEL") or None,
        deterministic=os.getenv("BACKEND_BATTLE_RL_DETERMINISTIC", "").lower()
        in {"1", "true", "yes", "on"},
        think_time=float(os.getenv("BACKEND_BATTLE_AI_THINK_TIME", "0")),
    )
    sender_task = asyncio.create_task(socket_sender(websocket, session))

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            payload = message.get("payload") or {}

            if action == "ping":
                await websocket.send_json({"action": "pong"})
                continue

            if action == "play_card":
                card_id = str(payload.get("card_id", "")).strip()
                try:
                    await session.submit_human_card(card_id)
                except ValueError as exc:
                    await websocket.send_json(
                        {
                            "action": "error",
                            "payload": {"message": str(exc)},
                        }
                    )
                continue

            if action == "restart_match":
                await session.restart_match()
                continue

            await websocket.send_json(
                {
                    "action": "error",
                    "payload": {"message": f"未知 action: {action}"},
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender_task
        await session.close()


if __name__ == "__main__":
    uvicorn.run("backend.app.api:app", host="127.0.0.1", port=8000, reload=False)
