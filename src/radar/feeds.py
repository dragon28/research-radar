"""Parse RSS 2.0 / RSS 1.0 (RDF) / Atom feeds into plain, safe items.

Feed content is untrusted: HTML is stripped, links must be http(s), and text is
only ever rendered as escaped Markdown, never executed or obeyed.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref")


class FeedError(ValueError):
    """The feed could not be parsed."""


@dataclass(frozen=True)
class Item:
    source: str
    title: str
    url: str
    guid: str
    published: datetime | None
    excerpt: str


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def shorten(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return cut + "…"


def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return url


def normalize_url(url: str) -> str:
    """Canonical form used for duplicate detection (not for display)."""
    p = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES)
    ]
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    found = el.find(path)
    return found.text if found is not None and found.text else None


def parse_feed(source: str, data: bytes | str) -> list[Item]:
    if isinstance(data, str):
        data = data.encode("utf-8")
    if b"<!ENTITY" in data[:4096]:
        raise FeedError(f"{source}: DTD entities are not allowed")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FeedError(f"{source}: not valid XML ({e})") from e

    if root.tag == f"{ATOM}feed":
        entries = root.findall(f"{ATOM}entry")
        raw = []
        for e in entries:
            link = None
            for ln in e.findall(f"{ATOM}link"):
                if ln.get("rel", "alternate") == "alternate":
                    link = ln.get("href")
                    break
            raw.append((
                _text(e, f"{ATOM}title"), link, _text(e, f"{ATOM}id"),
                _text(e, f"{ATOM}published") or _text(e, f"{ATOM}updated"),
                _text(e, f"{ATOM}summary") or _text(e, f"{ATOM}content"),
            ))
    elif root.tag in ("rss", "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"):
        entries = root.findall("./channel/item") + root.findall(f"{RSS1}item")
        raw = []
        for e in entries:
            ns = RSS1 if e.tag == f"{RSS1}item" else ""
            raw.append((
                _text(e, f"{ns}title"), _text(e, f"{ns}link"), _text(e, "guid"),
                _text(e, "pubDate") or _text(e, f"{DC}date"),
                _text(e, f"{ns}description") or _text(e, f"{CONTENT}encoded"),
            ))
    else:
        raise FeedError(f"{source}: unknown feed type <{root.tag}>")

    items = []
    for title, link, guid, date, summary in raw:
        url = safe_url(link)
        title = strip_html(title)
        if not url or not title:
            continue
        items.append(Item(
            source=source,
            title=shorten(title, 200),
            url=url,
            guid=(guid or "").strip() or url,
            published=parse_date(date),
            excerpt=shorten(strip_html(summary)),
        ))
    return items
