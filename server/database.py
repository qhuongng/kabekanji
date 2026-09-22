import json
import secrets
import sqlite3

from server.config import DB_PATH

DATABASE_URL = str(DB_PATH)

# Base32 alphabet without look-alikes (0/O, 1/I/L)
_TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_TOKEN_LENGTH = 8


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist"""
    with _connect() as db:
        db.executescript("""
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
        db.commit()


def token_exists(token: str) -> bool:
    """True if a user_config row exists for this token"""
    with _connect() as db:
        row = db.execute(
            "SELECT 1 FROM user_config WHERE token = ?", (token,)
        ).fetchone()
    return row is not None


def create_token() -> str:
    """Generate a fresh unique token and seed a default config row for it"""
    from server.config import DEFAULTS

    with _connect() as db:
        while True:
            token = "".join(
                secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LENGTH)
            )
            row = db.execute(
                "SELECT 1 FROM user_config WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                break

        db.execute(
            "INSERT INTO user_config (token, config) VALUES (?, ?)",
            (token, json.dumps(dict(DEFAULTS))),
        )
        db.commit()

    return token


def get_config(token: str) -> dict | None:
    """Return the config for a token, or None if the token doesn't exist"""
    from server.config import DEFAULTS

    with _connect() as db:
        row = db.execute(
            "SELECT config FROM user_config WHERE token = ?", (token,)
        ).fetchone()

    if row is None:
        return None
    saved = json.loads(row["config"])
    return {**DEFAULTS, **saved}


def get_kanji_by_char(character: str) -> dict | None:
    """Fetch a specific kanji by character without touching history"""
    with _connect() as db:
        row = db.execute(
            "SELECT * FROM kanji WHERE character = ?", (character,)
        ).fetchone()
    return dict(row) if row else None


def save_config(token: str, config: dict) -> None:
    """Upsert user config"""
    with _connect() as db:
        db.execute(
            """INSERT INTO user_config (token, config) VALUES (?, ?)
               ON CONFLICT(token) DO UPDATE SET config = excluded.config""",
            (token, json.dumps(config)),
        )
        db.commit()
