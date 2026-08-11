"""Per-user selection of the curated RSS source catalogue."""

from __future__ import annotations

import json

from db import connect, fetch_one
from utils.news import DEFAULT_SOURCE_IDS, normalise_source_ids


def get_news_source_ids(user_id: int | None) -> tuple[str, ...]:
    if not user_id:
        return DEFAULT_SOURCE_IDS
    try:
        row = fetch_one(
            "SELECT news_source_ids FROM fastvc.user_preferences WHERE user_id = %s",
            (user_id,),
        )
    except Exception:
        return DEFAULT_SOURCE_IDS
    values = row.get("news_source_ids") if row else None
    return normalise_source_ids(values if isinstance(values, list) else None)


def save_news_source_ids(user_id: int, source_ids: list[str]) -> tuple[str, ...]:
    selected = normalise_source_ids(source_ids)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fastvc.user_preferences (user_id, news_source_ids, updated_at)
               VALUES (%s, %s::jsonb, now())
               ON CONFLICT (user_id) DO UPDATE
               SET news_source_ids = EXCLUDED.news_source_ids, updated_at = now()""",
            (user_id, json.dumps(selected)),
        )
        conn.commit()
    return selected
