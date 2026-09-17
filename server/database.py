import aiosqlite
import json
from server.config import DB_PATH

DATABASE_URL = str(DB_PATH)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_URL)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS kanji (
                character TEXT PRIMARY KEY,
                meanings TEXT NOT NULL,         -- JSON array of English meanings
                on_yomi TEXT NOT NULL,          -- JSON array of on'yomi readings
                kun_yomi TEXT NOT NULL,         -- JSON array of kun'yomi readings
                sinovi TEXT DEFAULT '',         -- Sino-Vietnamese pronunciation
                stroke_count INTEGER DEFAULT 0,
                jlpt_level INTEGER DEFAULT 0,   -- 1-5 (0 = unassigned)
                grade INTEGER DEFAULT 0,        -- Jouyou grade (1-6, 8=secondary)
                vocabulary TEXT DEFAULT '[]',   -- JSON array of {word, reading, meaning, ...}
                radical TEXT DEFAULT ''         -- Classical radical character
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character TEXT NOT NULL,
                shown_date TEXT NOT NULL,       -- ISO date string YYYY-MM-DD
                token TEXT NOT NULL DEFAULT 'default',
                FOREIGN KEY (character) REFERENCES kanji(character)
            );

            CREATE INDEX IF NOT EXISTS idx_history_token_date
                ON history(token, shown_date DESC);

            CREATE TABLE IF NOT EXISTS user_config (
                token TEXT PRIMARY KEY,
                config TEXT NOT NULL            -- JSON blob of settings
            );
        """)
        await db.commit()


async def get_config(token: str) -> dict:
    """Retrieve user config, falling back to defaults."""
    from server.config import DEFAULTS

    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT config FROM user_config WHERE token = ?", (token,)
        )
        row = await cursor.fetchone()

    if row:
        saved = json.loads(row["config"])
        return {**DEFAULTS, **saved}
    return dict(DEFAULTS)


async def get_kanji_by_char(character: str) -> dict | None:
    """Fetch a specific kanji by character without touching history."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM kanji WHERE character = ?", (character,)
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def save_config(token: str, config: dict):
    """Upsert user config."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """INSERT INTO user_config (token, config) VALUES (?, ?)
               ON CONFLICT(token) DO UPDATE SET config = excluded.config""",
            (token, json.dumps(config)),
        )
        await db.commit()
