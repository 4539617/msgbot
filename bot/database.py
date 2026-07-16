import aiosqlite
from datetime import datetime

import os
DB_PATH = os.path.join(os.getenv("DATA_DIR", "/app/data"), "requests.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT,
                full_name   TEXT,
                transport   TEXT,
                reason      TEXT,
                description TEXT,
                media_ids   TEXT,
                status      TEXT DEFAULT 'new',
                created_at  TEXT NOT NULL,
                admin_reply TEXT
            )
        """)
        await db.commit()


async def create_request(
    user_id: int,
    username: str | None,
    full_name: str,
    transport: str,
    reason: str,
    description: str,
    media_ids: str,
) -> int:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO requests
                (user_id, username, full_name, transport, reason, description, media_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, transport, reason, description, media_ids, now),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_user_requests(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM requests WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_active_request(user_id: int) -> dict | None:
    """Возвращает активную заявку (new или in_work) если есть."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM requests WHERE user_id = ? AND status IN ('new', 'in_work') ORDER BY id DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_request(request_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM requests WHERE id = ?", (request_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_requests(status: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT * FROM requests WHERE status = ? ORDER BY id DESC", (status,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM requests ORDER BY id DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def set_reply(request_id: int, reply: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE requests SET admin_reply = ?, status = 'answered' WHERE id = ?",
            (reply, request_id),
        )
        await db.commit()


async def set_status(request_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE requests SET status = ? WHERE id = ?",
            (status, request_id),
        )
        await db.commit()
