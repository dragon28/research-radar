from datetime import UTC, datetime

import pytest

from radar.feeds import FeedError, normalize_url, parse_feed, safe_url, strip_html

RSS = """<rss version="2.0"><channel>
<item><title>A &amp; B</title><link>https://x.org/a</link><guid>g1</guid>
<pubDate>Wed, 28 Oct 2026 09:00:00 GMT</pubDate>
<description>&lt;b&gt;hi&lt;/b&gt;&lt;script&gt;evil()&lt;/script&gt;</description></item>
<item><title>No link</title></item>
<item><title>JS</title><link>javascript:alert(1)</link></item>
</channel></rss>"""


def test_rss_parsing_strips_html_and_bad_links():
    items = parse_feed("s", RSS)
    assert len(items) == 1
    it = items[0]
    assert it.title == "A & B"
    assert it.excerpt == "hi"
    assert it.published == datetime(2026, 10, 28, 9, tzinfo=UTC)


def test_atom_and_missing_date():
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>
    <link href="https://x.org/t"/><id>t1</id></entry></feed>"""
    (it,) = parse_feed("s", atom)
    assert it.url == "https://x.org/t" and it.published is None and it.guid == "t1"


def test_rss1_rdf():
    rdf = """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <item><title>R</title><link>https://x.org/r</link><dc:date>2026-10-01T00:00:00Z</dc:date></item></rdf:RDF>"""
    (it,) = parse_feed("s", rdf)
    assert it.published.year == 2026


@pytest.mark.parametrize("bad", ["<rss><channel>", "not xml", "<html></html>",
                                 '<!DOCTYPE x [<!ENTITY a "b">]><rss/>'])
def test_bad_feeds_raise(bad):
    with pytest.raises(FeedError):
        parse_feed("s", bad)


def test_url_helpers():
    assert normalize_url("http://WWW.X.org/a/?utm_source=rss&b=2") == "https://x.org/a?b=2"
    assert safe_url("ftp://x") is None and safe_url("https://x.org") == "https://x.org"
    assert strip_html("<p>a</p>  <i>b</i>") == "a b"
