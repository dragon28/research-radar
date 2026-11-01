from datetime import UTC, datetime

from radar.cli import main
from radar.digest import ingest, md_escape, render_post
from radar.store import Store

NOW = datetime(2026, 11, 1, 6, tzinfo=UTC)
RSS = """<rss><channel><item><title>{t}</title><link>{u}</link><guid>{g}</guid>
<pubDate>Fri, 30 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>"""


def feed(name, body, **kw):
    return {"name": name, "topic": "nano-technology", "status_code": 200, "body": body, **kw}


def test_failed_feed_does_not_stop_others(tmp_path):
    s = Store(tmp_path / "db")
    r = ingest(s, [feed("ok", RSS.format(t="Nano", u="https://x.org/1", g="1")),
                   feed("down", "", status_code=503),
                   feed("junk", "<rss>")], NOW)
    assert r.new == 1 and r.failed == ["down", "junk"]
    assert [f.error for f in r.feeds][1] == "HTTP 503"


def test_rerun_and_cross_feed_duplicates(tmp_path):
    s = Store(tmp_path / "db")
    a = feed("a", RSS.format(t="Same Story", u="https://x.org/1?utm_source=a", g="a1"))
    b = feed("b", RSS.format(t="same story!", u="https://y.org/other", g="b1"))
    first = ingest(s, [a, b], NOW)
    assert first.new == 1 and first.feeds[1].duplicates == 1
    assert ingest(s, [a, b], NOW).new == 0


def test_post_escapes_untrusted_text(tmp_path):
    s = Store(tmp_path / "db")
    ingest(s, [feed("a", RSS.format(t="{{ site.x }} [click](javascript:1) &lt;img&gt;",
                                    u="https://x.org/1", g="1"))], NOW)
    name, md = render_post(s, "2026-W44")
    assert name == "2026-11-01-research-radar-2026-w44.md"
    body = md.split("<!--more-->")[1]
    assert "{{" not in body and "<img" not in body and "\\[click\\]" in body
    assert "categories:\n    - nano-technology" in md


def test_empty_week_renders_nothing(tmp_path):
    assert render_post(Store(tmp_path / "db"), "2026-W44") is None


def test_md_escape():
    assert md_escape("a*b_[c]{d}") == "a\\*b\\_\\[c\\]&#123;d&#125;"


def test_demo_is_deterministic(tmp_path, capsys):
    import json
    args = ["demo", "--db", str(tmp_path / "d.sqlite"), "--out", str(tmp_path / "out")]
    main(args)
    r1 = json.loads(capsys.readouterr().out)
    post1 = (tmp_path / "out" / "2026-11-01-research-radar-2026-w44.md").read_text()
    main(args)
    r2 = json.loads(capsys.readouterr().out)
    assert r1 == r2 and r1["rerun_new_items"] == 0
    assert r1["new_items"] == 5 and r1["failed_feeds"] == ["Broken feed", "Offline feed"]
    assert post1 == (tmp_path / "out" / "2026-11-01-research-radar-2026-w44.md").read_text()
