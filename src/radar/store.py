"""SQLite store: every item is kept once, and each item belongs to one ISO week."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .feeds import Item, normalize_url

SCHEMA = """
create table if not exists items (
    url_key     text primary key,
    guid        text not null,
    title_key   text not null,
    source      text not null,
    topic       text not null,
    title       text not null,
    url         text not null,
    excerpt     text not null,
    published   text,
    first_seen  text not null,
    week        text not null
);
create index if not exists items_guid on items(guid);
create index if not exists items_title on items(title_key);
create index if not exists items_week on items(week);
"""


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def iso_week(dt: datetime) -> str:
    y, w, _ = dt.astimezone(UTC).isocalendar()
    return f"{y}-W{w:02d}"


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def is_duplicate(self, item: Item) -> bool:
        row = self.db.execute(
            "select 1 from items where url_key=? or guid=? or title_key=? limit 1",
            (normalize_url(item.url), item.guid, title_key(item.title)),
        ).fetchone()
        return row is not None

    def add(self, item: Item, topic: str, week: str, now: datetime) -> bool:
        if self.is_duplicate(item):
            return False
        self.db.execute(
            "insert into items values (?,?,?,?,?,?,?,?,?,?,?)",
            (
                normalize_url(item.url), item.guid, title_key(item.title), item.source,
                topic, item.title, item.url, item.excerpt,
                item.published.isoformat() if item.published else None,
                now.isoformat(), week,
            ),
        )
        return True

    def commit(self) -> None:
        self.db.commit()

    def week_items(self, week: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "select * from items where week=? order by topic, coalesce(published, first_seen) desc, title",
            (week,),
        ).fetchall()
