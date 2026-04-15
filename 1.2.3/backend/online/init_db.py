from __future__ import annotations

import asyncio

from .config import DB_PATH
from .service import OnlineRoomService


async def main() -> None:
    service = OnlineRoomService()
    await service.initialize()
    print(f"online room database initialized: {DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
