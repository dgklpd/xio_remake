from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from .config import DB_PATH, SCHEMA_PATH
from .models import PlayerIdentity, RoomListItemView, RoomRecord, RoomStatus


def _bool_to_int(value: bool) -> int:
    return 1 if value else 0


def _row_to_record(row: aiosqlite.Row | None) -> RoomRecord | None:
    if row is None:
        return None
    return RoomRecord(
        id=int(row["id"]),
        room_code=str(row["room_code"]),
        room_name=str(row["room_name"]),
        status=RoomStatus(str(row["status"])),
        host_token=str(row["host_token"]),
        guest_token=str(row["guest_token"]) if row["guest_token"] else None,
        host_user_id=str(row["host_user_id"]) if row["host_user_id"] else None,
        guest_user_id=str(row["guest_user_id"]) if row["guest_user_id"] else None,
        host_name=str(row["host_name"]),
        guest_name=str(row["guest_name"]) if row["guest_name"] else None,
        host_avatar=str(row["host_avatar"] or ""),
        guest_avatar=str(row["guest_avatar"]) if row["guest_avatar"] else None,
        host_connected=bool(row["host_connected"]),
        guest_connected=bool(row["guest_connected"]),
        host_ready=bool(row["host_ready"]),
        guest_ready=bool(row["guest_ready"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        expires_at=int(row["expires_at"]),
    )


class RoomRepository:
    def __init__(self, db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.read_text(encoding="utf-8")
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await self._ensure_columns(db)
            await db.commit()

    async def _ensure_columns(self, db: aiosqlite.Connection) -> None:
        cursor = await db.execute("PRAGMA table_info(rooms)")
        rows = await cursor.fetchall()
        existing = {str(row[1]) for row in rows}
        expected_columns = {
            "room_name": "ALTER TABLE rooms ADD COLUMN room_name TEXT NOT NULL DEFAULT '未命名房间'",
            "host_ready": "ALTER TABLE rooms ADD COLUMN host_ready INTEGER NOT NULL DEFAULT 0",
            "guest_ready": "ALTER TABLE rooms ADD COLUMN guest_ready INTEGER NOT NULL DEFAULT 0",
        }
        for column, sql in expected_columns.items():
            if column not in existing:
                await db.execute(sql)

    async def _connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        return db

    @asynccontextmanager
    async def _managed_connection(self):
        db = await self._connect()
        try:
            yield db
        finally:
            await db.close()

    async def create_room(
        self,
        *,
        room_code: str,
        room_name: str,
        host_identity: PlayerIdentity,
        host_token: str,
        expires_at: int,
    ) -> RoomRecord:
        now = int(time.time())
        async with self._managed_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO rooms (
                  room_code,
                  room_name,
                  status,
                  host_token,
                  host_user_id,
                  host_name,
                  host_avatar,
                  host_connected,
                  created_at,
                  updated_at,
                  expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room_code,
                    room_name,
                    RoomStatus.WAITING.value,
                    host_token,
                    host_identity.external_user_id,
                    host_identity.display_name,
                    host_identity.avatar_url,
                    1,
                    now,
                    now,
                    expires_at,
                ),
            )
            await db.commit()
            room_id = cursor.lastrowid
        room = await self.get_room_by_id(int(room_id))
        if room is None:
            raise RuntimeError("failed to load room after creation")
        return room

    async def get_room_by_code(self, room_code: str) -> RoomRecord | None:
        async with self._managed_connection() as db:
            cursor = await db.execute("SELECT * FROM rooms WHERE room_code = ?", (room_code,))
            row = await cursor.fetchone()
        return _row_to_record(row)

    async def get_room_by_id(self, room_id: int) -> RoomRecord | None:
        async with self._managed_connection() as db:
            cursor = await db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
            row = await cursor.fetchone()
        return _row_to_record(row)

    async def join_room(
        self,
        *,
        room_code: str,
        guest_identity: PlayerIdentity,
        guest_token: str,
        expires_at: int,
    ) -> RoomRecord | None:
        now = int(time.time())
        async with self._managed_connection() as db:
            await db.execute(
                """
                UPDATE rooms
                SET
                  status = ?,
                  guest_token = ?,
                  guest_user_id = ?,
                  guest_name = ?,
                  guest_avatar = ?,
                  guest_connected = 1,
                  updated_at = ?,
                  expires_at = ?
                WHERE room_code = ?
                  AND guest_token IS NULL
                  AND status = ?
                """,
                (
                    RoomStatus.FULL.value,
                    guest_token,
                    guest_identity.external_user_id,
                    guest_identity.display_name,
                    guest_identity.avatar_url,
                    now,
                    expires_at,
                    room_code,
                    RoomStatus.WAITING.value,
                ),
            )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def update_room_status(self, room_code: str, status: RoomStatus) -> RoomRecord | None:
        now = int(time.time())
        async with self._managed_connection() as db:
            await db.execute(
                "UPDATE rooms SET status = ?, updated_at = ? WHERE room_code = ?",
                (status.value, now, room_code),
            )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def update_connection_state(
        self,
        *,
        room_code: str,
        host_connected: bool | None = None,
        guest_connected: bool | None = None,
    ) -> RoomRecord | None:
        now = int(time.time())
        updates: list[str] = ["updated_at = ?"]
        params: list[object] = [now]
        if host_connected is not None:
            updates.append("host_connected = ?")
            params.append(_bool_to_int(host_connected))
        if guest_connected is not None:
            updates.append("guest_connected = ?")
            params.append(_bool_to_int(guest_connected))
        params.append(room_code)
        async with self._managed_connection() as db:
            await db.execute(
                f"UPDATE rooms SET {', '.join(updates)} WHERE room_code = ?",
                tuple(params),
            )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def update_ready_state(
        self,
        *,
        room_code: str,
        host_ready: bool | None = None,
        guest_ready: bool | None = None,
    ) -> RoomRecord | None:
        now = int(time.time())
        updates: list[str] = ["updated_at = ?"]
        params: list[object] = [now]
        if host_ready is not None:
            updates.append("host_ready = ?")
            params.append(_bool_to_int(host_ready))
        if guest_ready is not None:
            updates.append("guest_ready = ?")
            params.append(_bool_to_int(guest_ready))
        params.append(room_code)
        async with self._managed_connection() as db:
            await db.execute(
                f"UPDATE rooms SET {', '.join(updates)} WHERE room_code = ?",
                tuple(params),
            )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def remove_guest(self, room_code: str, *, expires_at: int) -> RoomRecord | None:
        now = int(time.time())
        async with self._managed_connection() as db:
            await db.execute(
                """
                UPDATE rooms
                SET
                  status = ?,
                  guest_token = NULL,
                  guest_user_id = NULL,
                  guest_name = NULL,
                  guest_avatar = NULL,
                  guest_connected = 0,
                  guest_ready = 0,
                  host_ready = 0,
                  updated_at = ?,
                  expires_at = ?
                WHERE room_code = ?
                """,
                (
                    RoomStatus.WAITING.value,
                    now,
                    expires_at,
                    room_code,
                ),
            )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def touch_room(self, room_code: str, *, expires_at: int | None = None) -> RoomRecord | None:
        now = int(time.time())
        async with self._managed_connection() as db:
            if expires_at is None:
                await db.execute(
                    "UPDATE rooms SET updated_at = ? WHERE room_code = ?",
                    (now, room_code),
                )
            else:
                await db.execute(
                    "UPDATE rooms SET updated_at = ?, expires_at = ? WHERE room_code = ?",
                    (now, expires_at, room_code),
                )
            await db.commit()
        return await self.get_room_by_code(room_code)

    async def delete_room(self, room_code: str) -> int:
        async with self._managed_connection() as db:
            cursor = await db.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
            await db.commit()
        return int(cursor.rowcount or 0)

    async def list_rooms(
        self,
        *,
        limit: int = 60,
        statuses: tuple[RoomStatus, ...] = (
            RoomStatus.WAITING,
            RoomStatus.FULL,
            RoomStatus.PLAYING,
        ),
    ) -> list[RoomListItemView]:
        now = int(time.time())
        placeholders = ", ".join("?" for _ in statuses)
        query = f"""
            SELECT *
            FROM rooms
            WHERE expires_at > ?
              AND status IN ({placeholders})
            ORDER BY
              CASE status
                WHEN 'waiting' THEN 0
                WHEN 'full' THEN 1
                WHEN 'playing' THEN 2
                ELSE 9
              END,
              updated_at DESC
            LIMIT ?
        """
        params: tuple[object, ...] = (now, *(status.value for status in statuses), limit)
        async with self._managed_connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        items: list[RoomListItemView] = []
        for row in rows:
            items.append(
                RoomListItemView(
                    room_code=str(row["room_code"]),
                    room_name=str(row["room_name"]),
                    status=RoomStatus(str(row["status"])),
                    created_at=int(row["created_at"]),
                    updated_at=int(row["updated_at"]),
                    expires_at=int(row["expires_at"]),
                    host_display_name=str(row["host_name"]),
                    guest_display_name=str(row["guest_name"]) if row["guest_name"] else None,
                    host_connected=bool(row["host_connected"]),
                    guest_connected=bool(row["guest_connected"]),
                    host_ready=bool(row["host_ready"]),
                    guest_ready=bool(row["guest_ready"]),
                )
            )
        return items

    async def delete_expired_rooms(self, *, now_ts: int | None = None) -> int:
        now = now_ts or int(time.time())
        async with self._managed_connection() as db:
            cursor = await db.execute("DELETE FROM rooms WHERE expires_at <= ?", (now,))
            await db.commit()
        return int(cursor.rowcount or 0)
