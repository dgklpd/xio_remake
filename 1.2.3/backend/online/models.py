from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RoomStatus(str, Enum):
    WAITING = "waiting"
    FULL = "full"
    PLAYING = "playing"
    FINISHED = "finished"
    CLOSED = "closed"


class RoomSeat(str, Enum):
    HOST = "host"
    GUEST = "guest"


class AuthProvider(str, Enum):
    GUEST = "guest"
    WECHAT = "wechat"


@dataclass(slots=True)
class PlayerIdentity:
    display_name: str
    avatar_url: str = ""
    auth_provider: AuthProvider = AuthProvider.GUEST
    external_user_id: str | None = None
    is_guest: bool = True


@dataclass(slots=True)
class RoomSeatState:
    seat: RoomSeat
    token: str | None
    user_id: str | None
    display_name: str
    avatar_url: str
    connected: bool
    ready: bool


@dataclass(slots=True)
class RoomRecord:
    id: int
    room_code: str
    room_name: str
    status: RoomStatus
    host_token: str
    guest_token: str | None
    host_user_id: str | None
    guest_user_id: str | None
    host_name: str
    guest_name: str | None
    host_avatar: str
    guest_avatar: str | None
    host_connected: bool
    guest_connected: bool
    host_ready: bool
    guest_ready: bool
    created_at: int
    updated_at: int
    expires_at: int


@dataclass(slots=True)
class RoomStateView:
    room_code: str
    room_name: str
    status: RoomStatus
    created_at: int
    updated_at: int
    expires_at: int
    host: RoomSeatState
    guest: RoomSeatState | None


@dataclass(slots=True)
class RoomListItemView:
    room_code: str
    room_name: str
    status: RoomStatus
    created_at: int
    updated_at: int
    expires_at: int
    host_display_name: str
    guest_display_name: str | None
    host_connected: bool
    guest_connected: bool
    host_ready: bool
    guest_ready: bool


@dataclass(slots=True)
class RoomCreateResult:
    room: RoomStateView
    seat: RoomSeat
    session_token: str


@dataclass(slots=True)
class RoomJoinResult:
    room: RoomStateView
    seat: RoomSeat
    session_token: str
