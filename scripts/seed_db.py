"""
Seed the SQLite database from data/kanji.json

Usage:
    python scripts/seed_db.py

All per-kanji data (meanings, readings, sinovi, radical, vocabulary) comes from
data/kanji.json
"""

import json
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "kanji.db"
KANJI_JSON_PATH = DATA_DIR / "kanji.json"


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kanji (
            character TEXT PRIMARY KEY,
            meanings TEXT NOT NULL,
            on_yomi TEXT NOT NULL,
            kun_yomi TEXT NOT NULL,
            sinovi TEXT DEFAULT '',
            stroke_count INTEGER DEFAULT 0,
            jlpt_level INTEGER DEFAULT 0,
            grade INTEGER DEFAULT 0,
            vocabulary TEXT DEFAULT '[]',
            radical TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character TEXT NOT NULL,
            shown_date TEXT NOT NULL,
            token TEXT NOT NULL DEFAULT 'default',
            FOREIGN KEY (character) REFERENCES kanji(character)
        );

        CREATE INDEX IF NOT EXISTS idx_history_token_date
            ON history(token, shown_date DESC);

        CREATE TABLE IF NOT EXISTS user_config (
            token TEXT PRIMARY KEY,
            config TEXT NOT NULL
        );
    """)


def load_kanji(conn: sqlite3.Connection):
    """Insert all jouyou kanji from kanji.json"""
    if not KANJI_JSON_PATH.exists():
        print(f"ERROR: {KANJI_JSON_PATH} not found.")
        print("Run: python scripts/extract_data.py")
        sys.exit(1)

    print(f"Loading kanji from {KANJI_JSON_PATH.name}...")
    with open(KANJI_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for character, entry in data.items():
        conn.execute(
            """INSERT OR REPLACE INTO kanji
               (character, meanings, on_yomi, kun_yomi, sinovi,
                stroke_count, jlpt_level, grade, vocabulary, radical)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                character,
                json.dumps(entry["meanings"]),
                json.dumps(entry["on_yomi"]),
                json.dumps(entry["kun_yomi"]),
                entry.get("sinovi", ""),
                entry.get("stroke_count", 0),
                entry.get("jlpt", 0),
                entry.get("grade", 0),
                json.dumps(entry.get("vocabulary", []), ensure_ascii=False),
                entry.get("radical", ""),
            ),
        )

    conn.commit()
    print(f"Inserted {len(data)} kanji.")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    load_kanji(conn)
    conn.close()

    print(f"Database saved to {DB_PATH}")


if __name__ == "__main__":
    main()
