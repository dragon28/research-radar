"""Turn feed responses into a weekly digest (a Jekyll post for dragon28.github.io)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .classify import TOPICS, classify
from .feeds import FeedError, parse_feed
from .store import Store, iso_week

MAX_AGE_DAYS = 14  # older items in a feed are skipped (feeds often keep months of history)


@dataclass
class FeedResult:
    name: str
    topic: str
    status: str  # ok | failed
    items: int = 0
    new: int = 0
    duplicates: int = 0
    too_old: int = 0
    error: str = ""


@dataclass
class RunReport:
    week: str
    feeds: list[FeedResult] = field(default_factory=list)
    week_total: int = 0
    by_topic: dict[str, int] = field(default_factory=dict)
    post_path: str | None = None

    @property
    def new(self) -> int:
        return sum(f.new for f in self.feeds)

    @property
    def failed(self) -> list[str]:
        return [f.name for f in self.feeds if f.status == "failed"]

    def as_dict(self) -> dict:
        return {
            "week": self.week,
            "new_items": self.new,
            "week_total": self.week_total,
            "by_topic": self.by_topic,
            "failed_feeds": self.failed,
            "post_path": self.post_path,
            "feeds": [f.__dict__ for f in self.feeds],
        }


def ingest(store: Store, feeds: list[dict], now: datetime) -> RunReport:
    """feeds: [{name, topic, status_code, body, error?}] as fetched by n8n or the CLI."""
    now = now.astimezone(UTC)
    week = iso_week(now)
    report = RunReport(week=week)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    for f in feeds:
        res = FeedResult(name=f["name"], topic=f["topic"], status="ok")
        report.feeds.append(res)
        code = f.get("status_code")
        if f.get("error") or code not in (200, None) or not f.get("body"):
            res.status = "failed"
            if f.get("error"):
                res.error = str(f["error"])[:200]
            elif code not in (200, None):
                res.error = f"HTTP {code}"
            else:
                res.error = "empty response"
            continue
        try:
            items = parse_feed(f["name"], f["body"])
        except FeedError as e:
            res.status, res.error = "failed", str(e)
            continue
        res.items = len(items)
        for it in items:
            if it.published and it.published < cutoff:
                res.too_old += 1
                continue
            topic = classify(it.title, it.excerpt, f["topic"])
            if store.add(it, topic, week, now):
                res.new += 1
            else:
                res.duplicates += 1
    store.commit()
    rows = store.week_items(week)
    report.week_total = len(rows)
    report.by_topic = {t: sum(r["topic"] == t for r in rows) for t in TOPICS}
    return report


def md_escape(text: str) -> str:
    """Escape Markdown, HTML and Liquid so feed text can't change the page."""
    text = text.replace("\\", "\\\\")
    text = re.sub(r"([`*_\[\]<>#|])", r"\\\1", text)
    return text.replace("{", "&#123;").replace("}", "&#125;")


def week_monday(week: str) -> date:
    y, w = week.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def render_post(store: Store, week: str) -> tuple[str, str] | None:
    """Returns (filename, markdown) or None when the week has no items."""
    rows = store.week_items(week)
    if not rows:
        return None
    monday = week_monday(week)
    sunday = monday + timedelta(days=6)
    counts = {t: sum(r["topic"] == t for r in rows) for t in TOPICS}
    sources = sorted({r["source"] for r in rows})
    present = [t for t in TOPICS if counts[t]]
    span = f"{monday:%-d %b} – {sunday:%-d %b %Y}"
    lines = [
        "---",
        "layout: page",
        'subheadline: "Research Radar"',
        f'title: "Research Radar: week {week[-2:]}, {monday.year}"',
        f'teaser: "{len(rows)} new science and technology stories collected for {span}."',
        "breadcrumb: true",
        "tags:",
        "    - research-radar",
        "categories:",
        *[f"    - {t}" for t in present],
        "---",
        "",
        f"New stories from {len(sources)} science news feeds for {span}, sorted by topic. "
        "Each entry links to the original article; the text under each title is a short "
        "excerpt from the publisher's feed, not a summary written by this site.",
        "",
        "<!--more-->",
        "",
    ]
    for t in present:
        lines += [f"## {TOPICS[t]} ({counts[t]})", ""]
        for r in rows:
            if r["topic"] != t:
                continue
            day = (r["published"] or r["first_seen"])[:10]
            lines.append(f"- [{md_escape(r['title'])}]({r['url']}) · {md_escape(r['source'])}, {day}")
            if r["excerpt"]:
                lines.append(f"  > {md_escape(r['excerpt'])}")
        lines.append("")
    lines += [
        "---",
        "",
        "*Collected automatically by [Research Radar](https://github.com/dragon28/research-radar) "
        "(n8n + Python) and published after manual review. Topic labels come from simple "
        "keyword rules and can be wrong; check the original article before relying on it.*",
        "",
    ]
    return f"{sunday:%Y-%m-%d}-research-radar-{week.lower()}.md", "\n".join(lines)


def write_post(store: Store, week: str, out_dir: Path) -> Path | None:
    rendered = render_post(store, week)
    if rendered is None:
        return None
    name, text = rendered
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return path
