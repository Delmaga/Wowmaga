import os
import time
import hmac
import hashlib
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "bot_data.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-moi-stp")

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    news_channel_id INTEGER
);

CREATE TABLE IF NOT EXISTS user_links (
    discord_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    battletag TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at INTEGER NOT NULL
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_INIT_SQL)
        await db.commit()


# ---------- Réglages serveur ----------

async def set_news_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_settings (guild_id, news_channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET news_channel_id=excluded.news_channel_id",
            (guild_id, channel_id),
        )
        await db.commit()


async def get_all_news_channels() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT news_channel_id FROM guild_settings WHERE news_channel_id IS NOT NULL") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ---------- Comptes liés (OAuth Battle.net) ----------

def sign_state(discord_id: int) -> str:
    sig = hmac.new(SECRET_KEY.encode(), str(discord_id).encode(), hashlib.sha256).hexdigest()[:20]
    return f"{discord_id}.{sig}"


def verify_state(state: str) -> int | None:
    try:
        discord_id_str, sig = state.split(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), discord_id_str.encode(), hashlib.sha256).hexdigest()[:20]
        if hmac.compare_digest(sig, expected):
            return int(discord_id_str)
    except Exception:
        pass
    return None


async def save_user_link(discord_id: int, region: str, access_token: str, refresh_token: str, expires_in: int, battletag: str | None = None):
    expires_at = int(time.time()) + expires_in
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_links (discord_id, region, battletag, access_token, refresh_token, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(discord_id) DO UPDATE SET region=excluded.region, battletag=excluded.battletag, "
            "access_token=excluded.access_token, refresh_token=excluded.refresh_token, expires_at=excluded.expires_at",
            (discord_id, region, battletag, access_token, refresh_token, expires_at),
        )
        await db.commit()


async def get_user_link(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT region, battletag, access_token, refresh_token, expires_at FROM user_links WHERE discord_id=?",
            (discord_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "region": row[0],
                "battletag": row[1],
                "access_token": row[2],
                "refresh_token": row[3],
                "expires_at": row[4],
            }


async def delete_user_link(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_links WHERE discord_id=?", (discord_id,))
        await db.commit()
