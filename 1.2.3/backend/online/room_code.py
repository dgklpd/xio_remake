from __future__ import annotations

import secrets

from .config import ROOM_CODE_ALPHABET, ROOM_CODE_LENGTH


def generate_room_code(length: int = ROOM_CODE_LENGTH) -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))


def validate_room_code(room_code: str, length: int = ROOM_CODE_LENGTH) -> bool:
    normalized = room_code.strip().upper()
    if len(normalized) != length:
        return False
    return all(char in ROOM_CODE_ALPHABET for char in normalized)


def normalize_room_code(room_code: str) -> str:
    return room_code.strip().upper()
