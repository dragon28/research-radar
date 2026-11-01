"""radar fetch | demo | serve  -- the same pipeline n8n drives, runnable without n8n."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .config import load_feeds
from .digest import ingest, write_post
from .server import serve
from .store import Store

UA = "research-radar/0.1 (+https://github.com/dragon28/research-radar)"


def fetch(url: str, timeout: float = 20, retries: int = 2) -> dict:
    last = ""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return {"status_code": r.status, "body": r.read(10 * 1024 * 1024).decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                return {"status_code": e.code, "body": "", "error": f"HTTP {e.code}"}
            last = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = str(e)
        time.sleep(2 ** attempt)
    return {"status_code": None, "body": "", "error": last or "fetch failed"}


def run(feeds: list[dict], db: str, out: str, now: datetime) -> dict:
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    try:
        report = ingest(store, feeds, now)
        path = write_post(store, report.week, Path(out))
        report.post_path = str(path) if path else None
    finally:
        store.close()
    return report.as_dict()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="radar")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "demo", "serve"):
        s = sub.add_parser(name)
        s.add_argument("--db", default="data/radar.sqlite" if name != "demo" else "out/demo.sqlite")
        s.add_argument("--out", default="out/posts" if name != "demo" else "out/demo")
        s.add_argument("--feeds", default="config/feeds.toml")
    sub.choices["serve"].add_argument("--host", default="127.0.0.1")
    sub.choices["serve"].add_argument("--port", type=int, default=8765)
    sub.choices["demo"].add_argument("--samples", default="sample_data")
    a = p.parse_args(argv)

    if a.cmd == "serve":
        return serve(a.host, a.port, a.db, a.out, a.feeds)
    if a.cmd == "fetch":
        feeds = [{**f, **fetch(f["url"])} for f in load_feeds(a.feeds)]
        report = run(feeds, a.db, a.out, datetime.now(UTC))
    else:  # demo: saved feeds, fixed clock, fresh database -> same output every time
        Path(a.db).unlink(missing_ok=True)
        manifest = json.loads(Path(a.samples, "manifest.json").read_text())
        now = datetime.fromisoformat(manifest["now"])
        feeds = []
        for f in manifest["feeds"]:
            path = Path(a.samples, f["file"])
            body = path.read_text(encoding="utf-8") if path.exists() else ""
            feeds.append({"name": f["name"], "topic": f["topic"],
                          "status_code": f.get("status_code", 200), "body": body})
        report = run(feeds, a.db, a.out, now)
        again = run(feeds, a.db, a.out, now)  # rerun must add nothing
        report["rerun_new_items"] = again["new_items"]
    print(json.dumps(report, indent=2))
