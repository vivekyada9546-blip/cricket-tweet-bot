"""Filters ke tests — freshness, relevance, junk, duplicates, images, copy limit."""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_news
from draft import cap_for_copy, make_styled_tweet
from filters import (
    FRESH_WINDOW,
    headline_hash,
    is_fresh,
    is_garbled,
    is_india_related,
    is_rejected,
    normalize_headline,
    should_accept,
)


def make_entry(title, minutes_ago=None, link="https://example.com/a", guid="guid-1", **extra):
    e = {"title": title, "link": link, "id": guid}
    if minutes_ago is not None:
        t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        e["published_parsed"] = t.timetuple()
    e.update(extra)
    return e


class TestFreshness(unittest.TestCase):
    def test_old_news_rejected(self):
        # 3 ghante purani news — reject
        ok, _ = should_accept(make_entry("Virat Kohli scores century", minutes_ago=200))
        self.assertFalse(ok)

    def test_missing_timestamp_rejected(self):
        ok, _ = should_accept(make_entry("India win series"))
        self.assertFalse(ok)

    def test_future_timestamp_rejected(self):
        ok, _ = should_accept(make_entry("India win series", minutes_ago=-30))
        self.assertFalse(ok)

    def test_fresh_accepted(self):
        ok, _ = should_accept(make_entry("Virat Kohli scores 76th century", minutes_ago=10))
        self.assertTrue(ok)

    def test_two_hour_boundary(self):
        self.assertTrue(is_fresh(make_entry("x", minutes_ago=110)))
        self.assertFalse(is_fresh(make_entry("x", minutes_ago=140)))


class TestRelevance(unittest.TestCase):
    def test_fresh_indian_player_news_accepted(self):
        ok, _ = should_accept(make_entry("Jasprit Bumrah ruled out of Test series with injury", minutes_ago=15))
        self.assertTrue(ok)

    def test_sri_lanka_vs_england_rejected(self):
        ok, _ = should_accept(make_entry("Sri Lanka vs England, 2nd Test, day 3 highlights", minutes_ago=10))
        self.assertFalse(ok)

    def test_australia_only_rejected(self):
        ok, _ = should_accept(make_entry("Australia announce 15-member squad for Ashes tour", minutes_ago=12))
        self.assertFalse(ok)

    def test_sponsorship_finance_ad_rejected(self):
        for title in [
            "RCB sign multi-year sponsorship deal worth crores",
            "IPL title rights valuation rises 40 percent",
            "MS Dhoni brand ambassador for new TV show ad campaign",
        ]:
            ok, _ = should_accept(make_entry(title, minutes_ago=8))
            self.assertFalse(ok, title)

    def test_probable_xi_and_rumours_rejected(self):
        for title in [
            "India probable XI for 1st ODI against West Indies",
            "Predicted XI: India likely to make two changes",
            "Rumours of BCCI mulling coaching change surface",
            "India vs West Indies Dream11 Prediction for the 1st ODI: Captain, vice-captain",
        ]:
            ok, _ = should_accept(make_entry(title, minutes_ago=8))
            self.assertFalse(ok, title)

    def test_garbled_encoded_rejected(self):
        ok, _ = should_accept(make_entry("Kohli \u00c3\u00a2\u20ac\u201d century %20 record \u00c3", minutes_ago=5))
        self.assertFalse(ok)
        self.assertTrue(is_garbled("%%%% !!!! ####"))

    def test_domestic_and_ipl_accepted(self):
        for title in [
            "Ranji Trophy: Mumbai beat Kerala by innings",
            "CSK retain Ruturaj Gaikwad for next IPL season",
            "Smriti Mandhana powers India Women to series win",
        ]:
            ok, _ = should_accept(make_entry(title, minutes_ago=20))
            self.assertTrue(ok, title)

    def test_non_cricket_india_news_rejected(self):
        # India keyword hai par cricket nahi — kabaddi, politics, tech
        for title in [
            "India women retain Asian Games kabaddi gold, beat Iran 37-34",
            "India calls for greater Global South voice, UNSC reform at G77",
            "The Global GCC Summit 2026 Puts AI, R&D and Digital Innovation at Centre",
        ]:
            ok, _ = should_accept(make_entry(title, minutes_ago=10))
            self.assertFalse(ok, title)


class TestDuplicates(unittest.TestCase):
    def test_same_headline_different_urls_duplicate(self):
        a = headline_hash("Kohli hits century! \U0001F3CF #TeamIndia")
        b = headline_hash("kohli hits century - Cricbuzz")
        c = headline_hash("Kohli   HITS century!!!")
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_different_headlines_not_duplicate(self):
        self.assertNotEqual(headline_hash("Kohli hits century"), headline_hash("Rohit hits double century"))

    def test_normalize_strips_urls_emoji_punctuation(self):
        self.assertEqual(
            normalize_headline("India win! https://t.co/abc \u26bd"),
            normalize_headline("India win"),
        )


class TestSeenState(unittest.TestCase):
    def test_seen_json_roundtrip_persist(self):
        old = fetch_news.STATE_FILE
        fetch_news.STATE_FILE = "/tmp/test_seen.json"
        try:
            seen = fetch_news.load_seen()
            self.assertEqual(seen, {"guids": [], "links": [], "heads": []})
            fetch_news.register(seen, "g1", "https://x/1", "h1")
            fetch_news.save_seen(seen)
            loaded = fetch_news.load_seen()
            self.assertEqual(loaded["guids"], ["g1"])
            self.assertEqual(loaded["links"], ["https://x/1"])
            self.assertEqual(loaded["heads"], ["h1"])
            # duplicate register -> no double entry
            fetch_news.register(loaded, "g1", "https://x/1", "h1")
            self.assertEqual(len(loaded["guids"]), 1)
            self.assertTrue(fetch_news.already_seen(loaded, "g1", "https://x/1", "h1"))
        finally:
            fetch_news.STATE_FILE = old
            if os.path.exists("/tmp/test_seen.json"):
                os.remove("/tmp/test_seen.json")


class TestImages(unittest.TestCase):
    def test_rss_image_media_content(self):
        e = {"media_content": [{"url": "https://img/1.jpg"}]}
        self.assertEqual(fetch_news.rss_image(e), "https://img/1.jpg")

    def test_rss_image_media_thumbnail(self):
        e = {"media_content": [], "media_thumbnail": [{"url": "https://img/2.jpg"}]}
        self.assertEqual(fetch_news.rss_image(e), "https://img/2.jpg")

    def test_rss_image_enclosure(self):
        e = {"enclosures": [{"type": "image/jpeg", "href": "https://img/3.jpg"}]}
        self.assertEqual(fetch_news.rss_image(e), "https://img/3.jpg")

    def test_rss_image_none(self):
        self.assertEqual(fetch_news.rss_image({}), "")


class TestCopyButton(unittest.TestCase):
    def test_copy_text_always_within_256(self):
        long_title = "India cricket team announcement " * 20
        draft = make_styled_tweet(long_title, "#TeamIndia #IndianCricket #IPL #INDvWI")
        self.assertLessEqual(len(cap_for_copy(draft)), 256)
        # mid-word cut nahi hona chahiye — end me word ya ellipsis
        self.assertTrue(cap_for_copy(draft).endswith(("\u2026",)) or
                        cap_for_copy(draft).split(" ")[-1].isalnum() or
                        cap_for_copy(draft).split(" ")[-1].startswith("#"))

    def test_short_draft_unchanged(self):
        draft = make_styled_tweet("India win", "#TeamIndia")
        self.assertEqual(cap_for_copy(draft), draft)

    def test_caption_contains_source_link(self):
        item = {"title": "India win series", "link": "https://example.com/story"}
        caption, copy_text = fetch_news.build_post(item, "#TeamIndia")
        self.assertIn("https://example.com/story", caption)
        self.assertLessEqual(len(copy_text), 256)


if __name__ == "__main__":
    unittest.main()
