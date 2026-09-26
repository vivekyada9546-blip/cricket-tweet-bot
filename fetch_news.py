"""
Cricket news fetcher v2 — GitHub Actions / cron के लिए one-shot script
====================================================================
- सिर्फ Indian cricket news (Team India, IPL, domestic, Indian players)
- सिर्फ पिछले 2 घंटे की fresh news (actual RSS timestamp से verify)
- duplicates रोकना: GUID + link + normalized headline hash
- जहाँ image मिले वहाँ photo के साथ post (RSS image → og:image → text fallback)
- Copy tweet button (Telegram की 256-char limit के अंदर)
- सिर्फ successful send के बाद item seen मार्क होता है (seen.json commit होता है)

चलाने के लिए env चाहिए: BOT_TOKEN, CHAT_ID
(optional: HASHTAGS, RSS_URLS, MAX_PER_RUN)

    python fetch_news.py
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import feedparser
import httpx
from dotenv import load_dotenv
from telegram import Bot, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from draft import cap_for_copy, copy_with_source, make_styled_tweet, smart_tags, strip_source
from filters import IST, entry_time, headline_hash, should_accept

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
TAGS = os.getenv("HASHTAGS", "#TeamIndia #IndianCricket").strip() or "#TeamIndia #IndianCricket"

# Sources: ESPNcricinfo (primary) + Google News India queries.
# Har source par wahi freshness + relevance filter lagta hai.
DEFAULT_FEEDS = ",".join([
    "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
    "https://news.google.com/rss/search?q=india+cricket+team+when:1h&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=india+playing+xi+OR+india+squad+when:2h&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=IPL+when:1h&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=ranji+trophy+OR+duleep+trophy+OR+irani+trophy+when:1h&hl=en-IN&gl=IN&ceid=IN:en",
])
FEEDS = [u.strip() for u in os.getenv("RSS_URLS", DEFAULT_FEEDS).split(",") if u.strip()]

STATE_FILE = os.getenv("STATE_FILE", "seen.json")
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN", "5"))
KEEP = 800        # har list me itni IDs yaad rakho
MAX_IMAGE = 5_000_000  # 5 MB — Telegram photo limit

OG_RE = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
TW_RE = r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']'

log = logging.getLogger("fetch_news")


# ---------- seen.json state ----------

def load_seen() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict) and all(k in data for k in ("guids", "links", "heads")):
        return data
    return {"guids": [], "links": [], "heads": []}


def save_seen(seen: dict) -> None:
    for key in ("guids", "links", "heads"):
        del seen[key][:-KEEP]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f)


def already_seen(seen: dict, guid: str, link: str, head_hash: str) -> bool:
    return (
        (guid and guid in seen["guids"])
        or (link and link in seen["links"])
        or (head_hash and head_hash in seen["heads"])
    )


def register(seen: dict, guid: str, link: str, head_hash: str) -> None:
    for key, val in (("guids", guid), ("links", link), ("heads", head_hash)):
        if val and val not in seen[key]:
            seen[key].append(val)


# ---------- image handling ----------

def rss_image(entry: dict) -> str:
    """RSS item se image URL (media_content → media_thumbnail → enclosure)."""
    for media in entry.get("media_content", []) or []:
        if media.get("url"):
            return media["url"]
    for thumb in entry.get("media_thumbnail", []) or []:
        if thumb.get("url"):
            return thumb["url"]
    for enc in entry.get("enclosures", []) or []:
        if str(enc.get("type", "")).startswith("image/") and enc.get("href"):
            return enc["href"]
    return ""


async def article_image(link: str) -> str:
    """Article page ka Open Graph / Twitter card image URL."""
    import re as _re
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(link)
        m = _re.search(OG_RE, r.text, _re.I) or _re.search(TW_RE, r.text, _re.I)
        return m.group(1) if m else ""
    except Exception:
        return ""


async def fetch_image_bytes(url: str):
    """Valid HTTP/HTTPS image download (content-type + size check). Fail → None."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    host = urlparse(url).hostname or ""
    # Google News sometimes exposes its own logo/placeholder as media content.
    # Never publish that generic image as if it were the article photo.
    if (host == "news.google.com" or host.endswith(".gstatic.com")
            or host.endswith(".googleusercontent.com")):
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image/") and len(r.content) <= MAX_IMAGE:
            return r.content
    except Exception:
        pass
    return None


async def default_image_resolver(item: dict):
    """Priority: RSS image → og:image / twitter image → None (text fallback)."""
    img = await fetch_image_bytes(item.get("image_url", ""))
    if img is not None:
        return img
    og = await article_image(item.get("link", ""))
    if og:
        img = await fetch_image_bytes(og)
        if img is not None:
            return img
    return None


# ---------- send ----------

def ist_str(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, IST).isoformat(timespec="seconds")


def build_post(item: dict, tags: str):
    """Return (caption, tweet_copy, source_copy)."""
    draft = make_styled_tweet(item["title"], smart_tags(item["title"], tags))
    caption = f"{draft}\n\nSource: {item['link']}" if item["link"] else draft
    tweet_copy = cap_for_copy(draft)
    source_copy, has_source = copy_with_source(draft, item.get("link", ""))
    return caption, tweet_copy, source_copy, has_source


async def send_one(bot, item: dict, chat_id: str, tags: str, img) -> bool:
    caption, tweet_copy, source_copy, has_source = build_post(item, tags)
    rows = [[InlineKeyboardButton("Copy tweet", copy_text=CopyTextButton(text=tweet_copy))]]
    if has_source and source_copy != tweet_copy:
        rows.append([InlineKeyboardButton("Copy with source", copy_text=CopyTextButton(text=source_copy))])
    keyboard = InlineKeyboardMarkup(rows)
    if img:
        await bot.send_photo(
            chat_id=chat_id, photo=img, caption=caption, reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id=chat_id, text=caption, reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    return True


async def deliver(bot, items, chat_id, tags, max_posts, image_resolver=None):
    """Fresh items me se max_posts tak bhejo. Return: successfully sent items."""
    if image_resolver is None:
        image_resolver = default_image_resolver
    sent = []
    for item in items[:max_posts]:
        try:
            img = await image_resolver(item)
            await send_one(bot, item, chat_id, tags, img)
        except Exception as exc:
            log.error("Send failed for %r: %s", item.get("title", "")[:60], exc)
            continue
        now = time.time()
        print("Sent:", item["title"][:70])
        print(f"Source time: {ist_str(item['epoch'])}")
        print(f"Send time: {ist_str(now)}")
        print(f"Delay: {int((now - item['epoch']) / 60)} minutes")
        print("Image: sent" if img else "Image: unavailable, text fallback used")
        sent.append(item)
    return sent


# ---------- main ----------

def collect_candidates(seen: dict):
    """सभी feeds पढ़ो, filters लगाओ, dedupe करो, newest-first sort करो।"""
    candidates = []
    seen_hashes_in_run = set()
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            log.error("Feed fail %s: %s", url, exc)
            continue
        for entry in feed.entries:
            ok, reason = should_accept(entry)
            if not ok:
                continue
            title = strip_source(entry.get("title", ""))
            head_hash = headline_hash(title)
            guid = entry.get("id") or entry.get("link") or title
            link = entry.get("link", "")
            if head_hash in seen_hashes_in_run:
                continue
            if already_seen(seen, guid, link, head_hash):
                continue
            seen_hashes_in_run.add(head_hash)
            candidates.append({
                "guid": guid,
                "title": title,
                "link": link,
                "hash": head_hash,
                "epoch": entry_time(entry),
                "image_url": rss_image(entry),
            })
    candidates.sort(key=lambda x: x["epoch"], reverse=True)
    return candidates


async def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("BOT_TOKEN / CHAT_ID missing — repo Secrets (या .env) में भरो।")

    seen = load_seen()
    candidates = collect_candidates(seen)

    if not candidates:
        print("No fresh, relevant Indian cricket news found.")
        return

    print(f"{len(candidates)} fresh relevant items, sending max {MAX_PER_RUN}.")

    bot = Bot(BOT_TOKEN)
    await bot.initialize()
    try:
        sent = await deliver(bot, candidates, CHAT_ID, TAGS, MAX_PER_RUN)
        # sirf successfully sent items ko seen mark karo
        for item in sent:
            register(seen, item["guid"], item["link"], item["hash"])
        print(f"Done: {len(sent)} sent, {len(candidates) - len(sent)} left for next run.")
    finally:
        save_seen(seen)
        await bot.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
