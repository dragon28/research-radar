"""Tiny local HTTP API that n8n calls. Binds to 127.0.0.1 only.

GET  /health   -> {"ok": true}
GET  /feeds    -> feed list from config/feeds.toml (n8n fetches each one)
POST /digest   -> body {"feeds": [{name, topic, status_code, body, error}]}
                  stores new items, writes the weekly draft post, returns a run report
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import load_feeds
from .digest import ingest, write_post
from .store import Store

MAX_BODY = 20 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "research-radar"
    cfg: dict = {}

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # quieter logs
        print(f"[radar] {self.command} {self.path} {args[1] if len(args) > 1 else ''}")

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path == "/feeds":
            return self._send(200, {"feeds": load_feeds(self.cfg["feeds"])})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/digest":
            return self._send(404, {"error": "not found"})
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > MAX_BODY:
            return self._send(413, {"error": "body missing or too large"})
        try:
            payload = json.loads(self.rfile.read(size))
            feeds = payload["feeds"]
            if not isinstance(feeds, list):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            return self._send(400, {"error": "expected JSON {\"feeds\": [...]}"})
        now = datetime.now(UTC)
        if payload.get("now"):
            now = datetime.fromisoformat(payload["now"])
        store = Store(self.cfg["db"])
        try:
            report = ingest(store, feeds, now)
            path = write_post(store, report.week, Path(self.cfg["out"]))
            report.post_path = str(path) if path else None
        finally:
            store.close()
        return self._send(200, report.as_dict())


def serve(host: str, port: int, db: str, out: str, feeds: str) -> None:
    if host not in ("127.0.0.1", "localhost") and not os.environ.get("RADAR_ALLOW_REMOTE"):
        raise SystemExit("refusing to bind outside localhost (set RADAR_ALLOW_REMOTE=1 to override)")
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    Handler.cfg = {"db": db, "out": out, "feeds": feeds}
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"[radar] listening on http://{host}:{port}")
    httpd.serve_forever()
