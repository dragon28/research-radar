from __future__ import annotations

import tomllib
from pathlib import Path

from .classify import TOPICS
from .feeds import safe_url


def load_feeds(path: str | Path) -> list[dict]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    feeds = []
    for f in data.get("feed", []):
        if f.get("topic") not in TOPICS:
            raise ValueError(f"feed {f.get('name')!r}: topic must be one of {list(TOPICS)}")
        if not safe_url(f.get("url")):
            raise ValueError(f"feed {f.get('name')!r}: url must be http(s)")
        feeds.append({"name": f["name"], "url": f["url"], "topic": f["topic"]})
    if not feeds:
        raise ValueError("no feeds configured")
    return feeds
