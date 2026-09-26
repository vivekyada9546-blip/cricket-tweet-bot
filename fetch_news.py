"""
Cricket news fetcher — GitHub Actions / cron के लिए one-shot script
====================================================================
RSS feeds (default: Google News cricket) से नई news पढ़ता है और
आपके Telegram पर tweet-ready draft (Copy button के साथ) भेजता है।
पुरानी news repeat न हों — इसलिए seen.json में IDs याद रखता है।

चलाने के लिए env चाहिए: BOT_TOKEN, CHAT_ID
(optional: HASHTAGS, RSS_URLS, MAX_PER_RUN)

    python fetch_news.py
"""

import asyncio
import json
import os

import feedparser
from dotenv import load_dotenv
from telegram import Bot, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from draft import make_styled_tweet, smart_tags, strip_source

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
TAGS = os.getenv("HASHTAGS", "#TeamIndia #IndianCricket").strip() or "#TeamIndia #IndianCricket"

# Default: सिर्फ Indian cricket — Team India, IPL, Indian domestic
DEFAULT_FEEDS = ",".join([
    "https://news.google.com/rss/search?q=india+cricket+team+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=india+playing+xi+OR+probable+xi+OR+india+squad+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=IPL+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=ranji+trophy+OR+duleep+trophy+OR+irani+trophy+OR+indian+domestic+cricket+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
])
FEEDS = [u.strip() for u in os.getenv("RSS_URLS", DEFAULT_FEEDS).split(",") if u.strip()]

STATE_FILE = os.getenv("STATE_FILE", "seen.json")
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN", "5"))
KEEP = 800  # seen.json में इतनी IDs रखो


def load_seen() -> list:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_seen(seen: list) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-KEEP:], f)


def collect_new_items(seen: list) -> list:
    """सभी feeds पढ़कर नए items की list [(guid, title, link), ...] देता है।"""
    items = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            guid = entry.get("id") or entry.get("link") or entry.get("title")
            if not guid or guid in seen:
                continue
            items.append(
                (guid, strip_source(entry.get("title", "")), entry.get("link", ""))
            )
    return items


async def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("BOT_TOKEN / CHAT_ID missing — repo Secrets (या .env) में भरो।")

    seen = load_seen()
    fresh = collect_new_items(seen)
    if not fresh:
        print("कोई नई news नहीं मिली।")
        return

    bot = Bot(BOT_TOKEN)
    await bot.initialize()
    try:
        for guid, title, link in fresh[:MAX_PER_RUN]:
            # breaking-news style tweet (headline + smart hashtags)
            tags = smart_tags(title, TAGS)
            draft = make_styled_tweet(title, tags)
            # link वाला वर्ज़न — अलग button से copy हो सकता है
            draft_with_link = make_styled_tweet(title, tags, link) if link else draft

            message = draft if not link else f"{draft}\n\nSource: {link}"
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Copy tweet", copy_text=CopyTextButton(text=draft)),
                    InlineKeyboardButton("Copy with link", copy_text=CopyTextButton(text=draft_with_link)),
                ]]
            )
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            print("भेजा:", title[:70])
        extra = len(fresh) - MAX_PER_RUN
        if extra > 0:
            print(f"{extra} और news मिलीं पर skip कीं (MAX_PER_RUN={MAX_PER_RUN})।")
    finally:
        save_seen(seen + [g for g, _, _ in fresh])
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
