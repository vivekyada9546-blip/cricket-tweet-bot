"""
Text को tweet-ready draft में बदलने वाला shared logic.
bot.py और fetch_news.py — दोनों इस्तेमाल करते हैं।
"""

import re

MAX_LEN = 280  # X की tweet limit


def clean_text(text: str) -> str:
    """Extra spaces/lines हटाकर text साफ करता है।"""
    t = (text or "").strip()
    t = t.replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def strip_source(title: str) -> str:
    """Google News के titles 'Headline - Source' format में आते हैं — source हटाता है।"""
    t = (title or "").strip()
    if " - " in t:
        head, _, src = t.rpartition(" - ")
        if len(head) >= 10 and len(src) <= 40:
            return head.strip()
    return t


def make_draft(text: str, tags: str = "#Cricket") -> str:
    """News text + hashtags को 280 characters के भीतर tweet draft बनाता है।"""
    body = clean_text(text)
    tail = f"\n\n{tags.strip()}" if tags and tags.strip() else ""

    if len(body) + len(tail) <= MAX_LEN:
        return (body + tail).strip()

    # लंबा text: काटकर ellipsis (…) लगाओ, बीच के शब्द पर कटेगा नहीं
    room = MAX_LEN - len(tail) - 1
    body = body[:room].rstrip()
    cut = body.rfind(" ")
    if cut > room // 2:
        body = body[:cut].rstrip()
    return body + "\u2026" + tail


# ---------- X-style breaking news tweet (siren वाला format) ----------

def smart_tags(title: str, base_tags: str = "#TeamIndia #IndianCricket") -> str:
    """Headline देखकर relevant hashtags जोड़ता है (IPL, Ranji, IND vs XX वगैरह)।"""
    tags = base_tags.strip()
    rules = [
        (r"\bIPL\b", "#IPL"),
        (r"\bRanji\b", "#RanjiTrophy"),
        (r"\bDuleep\b", "#DuleepTrophy"),
        (r"\bIrani\b", "#IraniTrophy"),
        (r"\b(women|INDW)\b", "#WomenInBlue"),
        (r"\bAsian Games\b", "#AsianGames2026"),
    ]
    for pat, tag in rules:
        if re.search(pat, title, re.I) and tag.lower() not in tags.lower():
            tags += " " + tag
    m = re.search(r"\bIND\s*(?:vs\.?|v\.?)\s*([A-Z]{2,3})\b", title)
    if m:
        match_tag = "#INDv" + m.group(1).upper()
        if match_tag.lower() not in tags.lower():
            tags += " " + match_tag
    return tags


def tweet_style(title: str) -> str:
    """News के type के अनुसार style — हर news BREAKING नहीं होती।"""
    t = title.lower()
    if re.search(
        r"\b(breaking|record|century|double century|five-wicket|fifer|hat-trick|"
        r"announc|retire|injur|suspend|sack|signs|beats|wins|thrash|storm|stun)\b", t
    ):
        return "breaking"
    if re.search(r"\b(squad|xi|playing 11|probable|team news)\b", t):
        return "xi"
    return "normal"


def make_styled_tweet(title: str, tags: str = "#TeamIndia #IndianCricket", link: str = "") -> str:
    """News के अनुसार styled tweet draft:

    breaking -> siren-emoji {headline} siren-emoji
    XI/squad -> bat-emoji {headline}
    normal   -> {headline}
    और नीचे flag-emoji {hashtags}
    """
    t = clean_text(title)
    if not t:
        return ""
    style = tweet_style(t)
    if style == "breaking":
        body = f"\U0001F6A8 {t} \U0001F6A8"
    elif style == "xi":
        body = f"\U0001F3CF {t}"
    else:
        body = t
    if link:
        body += f"\n\n\U0001F517 {link}"
    tail = f"\U0001F1EE\U0001F1F3 {tags}" if tags and tags.strip() else ""
    return make_draft(body, tail)
