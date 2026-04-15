from __future__ import annotations

import asyncio
import secrets
import time

from .config import ROOM_EXPIRE_SECONDS, SESSION_TOKEN_BYTES
from .models import (
    PlayerIdentity,
    RoomCreateResult,
    RoomJoinResult,
    RoomListItemView,
    RoomRecord,
    RoomSeat,
    RoomSeatState,
    RoomStateView,
    RoomStatus,
)
from .repository import RoomRepository
from .room_code import generate_room_code, normalize_room_code, validate_room_code


class OnlineRoomError(Exception):
    pass


class InvalidRoomCodeError(OnlineRoomError):
    pass


class RoomNotFoundError(OnlineRoomError):
    pass


class RoomFullError(OnlineRoomError):
    pass


class RoomClosedError(OnlineRoomError):
    pass


class RoomExpiredError(OnlineRoomError):
    pass


class OnlineRoomService:
    def __init__(
        self,
        repository: RoomRepository | None = None,
        *,
        room_expire_seconds: int = ROOM_EXPIRE_SECONDS,
    ):
        self.repository = repository or RoomRepository()
        self.room_expire_seconds = room_expire_seconds
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await self.repository.initialize()

    def _next_expire_ts(self) -> int:
        return int(time.time()) + self.room_expire_seconds

    def _new_session_token(self) -> str:
        return secrets.token_urlsafe(SESSION_TOKEN_BYTES)

    def _build_default_room_name(self, identity: PlayerIdentity) -> str:
        display_name = identity.display_name.strip() or "房主"
        return f"{display_name}的房间"

    def _to_view(self, room: RoomRecord) -> RoomStateView:
        guest = None
        if room.guest_token is not None:
            guest = RoomSeatState(
                seat=RoomSeat.GUEST,
                token=room.guest_token,
                user_id=room.guest_user_id,
                display_name=room.guest_name or "玩家2",
                avatar_url=room.guest_avatar or "",
                connected=room.guest_connected,
                ready=room.guest_ready,
            )

        return RoomStateView(
            room_code=room.room_code,
            room_name=room.room_name,
            status=room.status,
            created_at=room.created_at,
            updated_at=room.updated_at,
            expires_at=room.expires_at,
            host=RoomSeatState(
                seat=RoomSeat.HOST,
                token=room.host_token,
                user_id=room.host_user_id,
                display_name=room.host_name,
                avatar_url=room.host_avatar,
                connected=room.host_connected,
                ready=room.host_ready,
            ),
            guest=guest,
        )

    async def create_room(
        self,
        host_identity: PlayerIdentity | None = None,
        *,
        room_name: str | None = None,
    ) -> RoomCreateResult:
        identity = host_identity or PlayerIdentity(display_name="房主")
        normalized_room_name = (room_name or "").strip() or self._build_default_room_name(identity)

        async with self._lock:
            await self.repository.delete_expired_rooms()
            room: RoomRecord | None = None
            for _ in range(12):
                room_code = generate_room_code()
                existing = await self.repository.get_room_by_code(room_code)
                if existing is None:
                    room = await self.repository.create_room(
                        room_code=room_code,
                        room_name=normalized_room_name[:24],
                        host_identity=identity,
                        host_token=self._new_session_token(),
                        expires_at=self._next_expire_ts(),
                    )
                    break
            if room is None:
                raise OnlineRoomError("unable to allocate room code")

        return RoomCreateResult(
            room=self._to_view(room),
            seat=RoomSeat.HOST,
            session_token=room.host_token,
        )

    async def list_rooms(self, *, limit: int = 60) -> list[RoomListItemView]:
        await self.repository.delete_expired_rooms()
        return await self.repository.list_rooms(limit=limit)

    async def join_room(
        self,
        room_code: str,
        guest_identity: PlayerIdentity | None = None,
    ) -> RoomJoinResult:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        identity = guest_identity or PlayerIdentity(display_name="玩家2")

        async with self._lock:
            await self.repository.delete_expired_rooms()
            room = await self.repository.get_room_by_code(normalized)
            if room is None:
                raise RoomNotFoundError("room not found")
            if room.expires_at <= int(time.time()):
                await self.repository.delete_room(normalized)
                raise RoomExpiredError("room expired")
            if room.status in {RoomStatus.CLOSED, RoomStatus.FINISHED}:
                raise RoomClosedError("room is not joinable")
            if room.guest_token is not None:
                raise RoomFullError("room is full")

            updated = await self.repository.join_room(
                room_code=normalized,
                guest_identity=identity,
                guest_token=self._new_session_token(),
                expires_at=self._next_expire_ts(),
            )
            if updated is None or updated.guest_token is None:
                raise OnlineRoomError("failed to join room")

        return RoomJoinResult(
            room=self._to_view(updated),
            seat=RoomSeat.GUEST,
            session_token=updated.guest_token,
        )

    async def get_room_state(self, room_code: str) -> RoomStateView:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        await self.repository.delete_expired_rooms()
        room = await self.repository.get_room_by_code(normalized)
        if room is None:
            raise RoomNotFoundError("room not found")
        if room.expires_at <= int(time.time()):
            await self.repository.delete_room(normalized)
            raise RoomExpiredError("room expired")
        return self._to_view(room)

    async def set_room_status(self, room_code: str, status: RoomStatus) -> RoomStateView:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        async with self._lock:
            room = await self.repository.get_room_by_code(normalized)
            if room is None:
                raise RoomNotFoundError("room not found")
            if room.expires_at <= int(time.time()):
                await self.repository.delete_room(normalized)
                raise RoomExpiredError("room expired")
            updated = await self.repository.update_room_status(normalized, status)
            if updated is None:
                raise RoomNotFoundError("room not found")
        return self._to_view(updated)

    async def set_ready(self, room_code: str, seat: RoomSeat, ready: bool) -> RoomStateView:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        async with self._lock:
            room = await self.repository.get_room_by_code(normalized)
            if room is None:
                raise RoomNotFoundError("room not found")
            if room.expires_at <= int(time.time()):
                await self.repository.delete_room(normalized)
                raise RoomExpiredError("room expired")
            if room.status in {RoomStatus.CLOSED, RoomStatus.FINISHED}:
                raise RoomClosedError("room is not available")
            if seat is RoomSeat.GUEST and room.guest_token is None:
                raise RoomNotFoundError("guest seat is empty")

            updated = await self.repository.update_ready_state(
                room_code=normalized,
                host_ready=ready if seat is RoomSeat.HOST else None,
                guest_ready=ready if seat is RoomSeat.GUEST else None,
            )
            if updated is None:
                raise RoomNotFoundError("room not found")
        return self._to_view(updated)

    async def set_connection_state(self, room_code: str, seat: RoomSeat, connected: bool) -> RoomStateView:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        async with self._lock:
            room = await self.repository.get_room_by_code(normalized)
            if room is None:
                raise RoomNotFoundError("room not found")
            if room.expires_at <= int(time.time()):
                await self.repository.delete_room(normalized)
                raise RoomExpiredError("room expired")
            if seat is RoomSeat.GUEST and room.guest_token is None:
                raise RoomNotFoundError("guest seat is empty")

            updated = await self.repository.update_connection_state(
                room_code=normalized,
                host_connected=connected if seat is RoomSeat.HOST else None,
                guest_connected=connected if seat is RoomSeat.GUEST else None,
            )
            if updated is None:
                raise RoomNotFoundError("room not found")
        return self._to_view(updated)

    async def leave_room(self, room_code: str, seat: RoomSeat) -> RoomStateView | None:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        async with self._lock:
            room = await self.repository.get_room_by_code(normalized)
            if room is None:
                raise RoomNotFoundError("room not found")
            await self.repository.delete_room(normalized)
            return None

    async def close_room(self, room_code: str) -> None:
        normalized = normalize_room_code(room_code)
        if not validate_room_code(normalized):
            raise InvalidRoomCodeError("invalid room code")

        async with self._lock:
            await self.repository.delete_room(normalized)

    async def cleanup_expired_rooms(self) -> int:
        async with self._lock:
            return await self.repository.delete_expired_rooms()
