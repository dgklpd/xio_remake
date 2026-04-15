"""Multiplayer room system package."""

from .manager import RoomManager
from .models import (
    AuthProvider,
    PlayerIdentity,
    RoomCreateResult,
    RoomJoinResult,
    RoomListItemView,
    RoomSeat,
    RoomStateView,
    RoomStatus,
)
from .repository import RoomRepository
from .service import (
    InvalidRoomCodeError,
    OnlineRoomError,
    OnlineRoomService,
    RoomClosedError,
    RoomExpiredError,
    RoomFullError,
    RoomNotFoundError,
)

__all__ = [
    "AuthProvider",
    "InvalidRoomCodeError",
    "OnlineRoomError",
    "OnlineRoomService",
    "PlayerIdentity",
    "RoomManager",
    "RoomClosedError",
    "RoomCreateResult",
    "RoomExpiredError",
    "RoomFullError",
    "RoomJoinResult",
    "RoomListItemView",
    "RoomNotFoundError",
    "RoomRepository",
    "RoomSeat",
    "RoomStateView",
    "RoomStatus",
]
