import random
from datetime import datetime, timedelta

import aiosqlite

from server.config import DB_PATH


async def select_kanji(token: str, config: dict) -> dict | None:
    """Pick a random kanji not shown to this token within the recency window,
    record it, and return it. Falls back to the least-recently-shown kanji if
    every kanji has been shown within the window
    """
    now = datetime.now()
    recency_window = int(config.get("recency_window", 5))
    cutoff = (now - timedelta(days=recency_window)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT k.* FROM kanji k
            WHERE k.character NOT IN (
                SELECT h.character FROM history h
                WHERE h.token = ? AND h.shown_date >= ?
            )
            """,
            (token, cutoff),
        )
        candidates = await cursor.fetchall()

        if candidates:
            chosen = random.choice(candidates)
        else:
            # All kanji shown within the window; fall back to least-recently-shown
            cursor = await db.execute(
                """
                SELECT k.* FROM kanji k
                LEFT JOIN (
                    SELECT character, MAX(shown_date) AS last_shown
                    FROM history WHERE token = ?
                    GROUP BY character
                ) h ON k.character = h.character
                ORDER BY h.last_shown ASC NULLS FIRST
                LIMIT 1
                """,
                (token,),
            )
            chosen = await cursor.fetchone()

        if not chosen:
            return None

        # Prune history rows older than the recency window for this token
        await db.execute(
            "DELETE FROM history WHERE token = ? AND shown_date < ?",
            (token, cutoff),
        )

        await db.execute(
            "INSERT INTO history (character, shown_date, token) VALUES (?, ?, ?)",
            (chosen["character"], now.isoformat(), token),
        )
        await db.commit()

        return dict(chosen)
