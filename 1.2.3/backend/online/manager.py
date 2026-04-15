from __future__ import annotations

import asyncio

from .models import PlayerIdentity, RoomCreateResult, RoomJoinResult, RoomSeat, RoomStateView
from .service import OnlineRoomService
from .session import RoomSession


class RoomManager:
    def __init__(self, service: OnlineRoomService | None = None):
        self.service = service or OnlineRoomService()
        self._sessions: dict[str, RoomSession] = {}
        self._lock = asyncio.Lock()

    async def _drop_session(self, room_code: str) -> None:
        async with self._lock:
            self._sessions.pop(room_code, None)

    async def initialize(self) -> None:
        await self.service.initialize()

    async def create_room(
        self,
        host_identity: PlayerIdentity | None = None,
        *,
        room_name: str | None = None,
    ) -> RoomCreateResult:
        async with self._lock:
            result = await self.service.create_room(host_identity, room_name=room_name)
            self._sessions[result.room.room_code] = RoomSession(
                self.service,
                result.room,
                on_room_closed=self._drop_session,
            )
            return result

    async def join_room(self, room_code: str, guest_identity: PlayerIdentity | None = None) -> RoomJoinResult:
        async with self._lock:
            result = await self.service.join_room(room_code, guest_identity)
            session = self._sessions.get(result.room.room_code)
            if session is None:
                self._sessions[result.room.room_code] = RoomSession(
                    self.service,
                    result.room,
                    on_room_closed=self._drop_session,
                )
            else:
                await session.refresh()
            return result

    async def get_session(self, room_code: str) -> RoomSession:
        async with self._lock:
            session = self._sessions.get(room_code)
            if session is not None:
                return session
            room_state = await self.service.get_room_state(room_code)
            session = RoomSession(self.service, room_state, on_room_closed=self._drop_session)
            self._sessions[room_code] = session
            return session

    async def get_room_state(self, room_code: str) -> RoomStateView:
        session = await self.get_session(room_code)
        return session.state

    async def set_ready(self, room_code: str, seat: RoomSeat, ready: bool) -> RoomStateView:
        session = await self.get_session(room_code)
        return await session.set_ready(seat, ready)

    async def leave_room(self, room_code: str, seat: RoomSeat) -> RoomStateView | None:
        session = await self.get_session(room_code)
        next_state = await session.leave(seat)
        if next_state is None:
            async with self._lock:
                self._sessions.pop(room_code, None)
            return None
        return next_state

    async def close_room(self, room_code: str) -> None:
        async with self._lock:
            session = self._sessions.pop(room_code, None)
        if session is not None:
            await session.close()
        else:
            await self.service.close_room(room_code)

    async def cleanup_expired_rooms(self) -> int:
        removed = await self.service.cleanup_expired_rooms()
        if removed:
            async with self._lock:
                stale_codes = list(self._sessions.keys())
            for room_code in stale_codes:
                try:
                    await self.service.get_room_state(room_code)
                except Exception:
                    async with self._lock:
                        self._sessions.pop(room_code, None)
        return removed
