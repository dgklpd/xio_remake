from __future__ import annotations

from pathlib import Path


ONLINE_DIR = Path(__file__).resolve().parent
DATA_DIR = ONLINE_DIR / "data"
DB_PATH = DATA_DIR / "rooms.sqlite3"
SCHEMA_PATH = ONLINE_DIR / "schema.sql"

ROOM_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
ROOM_CODE_LENGTH = 6
ROOM_EXPIRE_SECONDS = 15 * 60
SESSION_TOKEN_BYTES = 24
