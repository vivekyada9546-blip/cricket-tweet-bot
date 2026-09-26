"""deliver() ke tests — send flow, max posts, failed send, no filler."""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_news


def make_item(i, minutes_ago=10):
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "guid": f"guid-{i}",
        "title": f"India cricket news number {i}",
        "link": f"https://example.com/{i}",
        "hash": f"hash-{i}",
        "epoch": t.timestamp(),
        "image_url": "",
    }


class FakeBot:
    """Send fail bhi kar sakta hai; har button 256-char limit validate karta hai."""

    def __init__(self, fail=False):
        self.fail = fail
        self.photos = 0
        self.messages = 0
        self.payloads = []

    def _check(self, kwargs):
        kb = kwargs["reply_markup"].inline_keyboard
        for row in kb:
            for button in row:
                assert len(button.copy_text.text) <= 256, "copy_text > 256 chars!"

    async def send_photo(self, **kw):
        if self.fail:
            raise RuntimeError("send failed")
        self._check(kw)
        self.photos += 1
        self.payloads.append(kw.get("caption", ""))

    async def send_message(self, **kw):
        if self.fail:
            raise RuntimeError("send failed")
        self._check(kw)
        self.messages += 1
        self.payloads.append(kw.get("text", ""))


async def no_image(item):
    return None


async def yes_image(item):
    return b"\x89PNG fake-image-bytes"


class TestDeliver(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_max_five_posts(self):
        items = [make_item(i) for i in range(8)]
        bot = FakeBot()
        sent = self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertEqual(len(sent), 5)
        self.assertEqual(bot.messages, 5)
        self.assertEqual(bot.photos, 0)

    def test_no_filler_when_empty(self):
        bot = FakeBot()
        sent = self.run_async(
            fetch_news.deliver(bot, [], "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertEqual(sent, [])
        self.assertEqual(bot.messages + bot.photos, 0)

    def test_only_one_genuine_item_sends_one(self):
        items = [make_item(1)]
        bot = FakeBot()
        sent = self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual(bot.messages, 1)

    def test_failed_send_not_marked_seen(self):
        """deliver() sirf successful items return karta hai —
        main() unhi ko seen register karta hai. Fail hone par seen me kuch nahi jata."""
        items = [make_item(i) for i in range(3)]
        bot = FakeBot(fail=True)
        sent = self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertEqual(sent, [])
        seen = fetch_news.load_seen()
        for item in items:
            self.assertFalse(fetch_news.already_seen(seen, item["guid"], item["link"], item["hash"]))

    def test_image_sent_with_photo(self):
        items = [make_item(1)]
        bot = FakeBot()
        sent = self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=yes_image)
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual(bot.photos, 1)
        self.assertEqual(bot.messages, 0)  # duplicate text message nahi

    def test_image_fail_text_fallback(self):
        items = [make_item(1)]
        bot = FakeBot()
        sent = self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual(bot.messages, 1)  # text fallback
        self.assertEqual(bot.photos, 0)

    def test_caption_has_source_and_copy_button_safe(self):
        items = [make_item(1)]
        bot = FakeBot()
        self.run_async(
            fetch_news.deliver(bot, items, "@chan", "#TeamIndia", 5, image_resolver=no_image)
        )
        self.assertIn("https://example.com/1", bot.payloads[0])
        # FakeBot._check ne already verify kar diya: copy_text hamesha <= 256


if __name__ == "__main__":
    unittest.main()
