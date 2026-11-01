import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from radar.server import Handler


def test_http_api(tmp_path):
    Handler.cfg = {"db": str(tmp_path / "db"), "out": str(tmp_path / "out"),
                   "feeds": "config/feeds.toml"}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        feeds = json.load(urllib.request.urlopen(base + "/feeds"))["feeds"]
        assert len(feeds) >= 5
        rss = ("<rss><channel><item><title>Graphene</title><link>https://x.org/g</link>"
               "<pubDate>Fri, 30 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>")
        body = json.dumps({"now": "2026-11-01T06:00:00+00:00", "feeds": [
            {"name": "n", "topic": "nano-technology", "status_code": 200, "body": rss}]}).encode()
        req = urllib.request.Request(base + "/digest", data=body,
                                     headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req))
        assert r["new_items"] == 1 and r["post_path"].endswith("2026-w44.md")
        bad = urllib.request.Request(base + "/digest", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(bad)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        srv.shutdown()
