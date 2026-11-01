import pytest

from radar.classify import classify


def test_keywords_beat_feed_default():
    assert classify("Graphene nanopore membrane", "", "bio-technology") == "nano-technology"


def test_no_match_uses_feed_default():
    assert classify("Weekly roundup", "misc", "chemical-technology") == "chemical-technology"


def test_tie_prefers_feed_default():
    assert classify("protein chip", "", "computer-technology") == "computer-technology"


def test_unknown_default_rejected():
    with pytest.raises(ValueError):
        classify("x", "", "astrology")
