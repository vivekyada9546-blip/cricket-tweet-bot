"""
Indian-cricket news filters — freshness, relevance, junk/garbled, duplicates.
fetch_news.py aur tests — dono yeh module use karte hain.
"""

import calendar
import hashlib
import re
import time
from datetime import timedelta, timezone

from draft import strip_source

FRESH_WINDOW = 2 * 60 * 60  # sirf pichle 2 ghante ki news
IST = timezone(timedelta(hours=5, minutes=30), name="IST")

# ---------- Indian cricket se direct connection ----------
INDIA_PATTERNS = [
    r"\bIndia\b", r"\bIndian\b", r"\bIND\b", r"\bTeam ?India\b", r"\bMen in Blue\b",
    r"\bBCCI\b", r"\bNCA\b", r"\bIPL\b", r"\bWPL\b", r"\bIndia [AU]\b", r"\bU-?19\b",
    r"\bRanji\b", r"\bDuleep\b", r"\bIrani\b", r"\bVijay Hazare\b",
    r"\bSyed Mushtaq Ali\b", r"\bDeodhar\b",
    r"\b(RCB|CSK|MI|KKR|RR|SRH|DC|PBKS|GT|LSG)\b",
    r"\b(Royal Challengers|Chennai Super Kings|Mumbai Indians|Kolkata Knight Riders|"
    r"Rajasthan Royals|Sunrisers Hyderabad|Delhi Capitals|Punjab Kings|Gujarat Titans|"
    r"Lucknow Super Giants)\b",
]

PLAYER_NAMES = [
    # men
    "Virat Kohli", "Rohit Sharma", "Shubman Gill", "Jasprit Bumrah", "Rishabh Pant",
    "Ravindra Jadeja", "KL Rahul", "Hardik Pandya", "Suryakumar Yadav", "Mohammed Siraj",
    "Mohammed Shami", "Axar Patel", "Yashasvi Jaiswal", "Shreyas Iyer", "Kuldeep Yadav",
    "Arshdeep Singh", "Ishan Kishan", "Sanju Samson", "Tilak Varma", "Rinku Singh",
    "Washington Sundar", "Prasidh Krishna", "Harshit Rana", "Nitish Kumar Reddy",
    "Abhishek Sharma", "Krunal Pandya", "Mohit Rathee", "Gautam Gambhir",
    "Ajit Agarkar", "VVS Laxman", "Cheteshwar Pujara", "Ajinkya Rahane", "Karun Nair",
    # women
    "Harmanpreet Kaur", "Smriti Mandhana", "Jemimah Rodrigues", "Deepti Sharma",
    "Shafali Verma", "Renuka Singh", "Richa Ghosh", "Amanjot Kaur", "Sneh Rana",
    "Pooja Vastrakar", "Radha Yadav", "Rajeshwari Gayakwad", "Taniya Bhatia",
]

# ---------- Reject patterns (India ho tab bhi na bhejo) ----------
REJECT_PATTERNS = [
    r"\bsponsor(ship)?\b", r"\bbrand ambassador\b", r"\bad ?campaign\b", r"\badvertis",
    r"\btitle rights\b", r"\bbroadcast(ing)? rights\b", r"\bnet ?worth\b",
    r"\bvaluation\b", r"\bbusiness\b", r"\bTV show\b", r"\bweb series\b",
    r"\bpodcast\b", r"\bmeme\b", r"\bpolls?\b",
    r"\b(probable|predicted|expected|likely)\s+(XI|eleven|11)\b",
    r"\brumou?rs?\b", r"\bunconfirmed\b",
    r"\bDream11\b", r"\bfantasy\b", r"\b(betting|odds)\b",
    r"\bmedals? tally\b", r"\bcommentary\b", r"\bscorecard\b",
    r"\blive (cricket )?score\b", r"\brecords? & stats\b",
    r"\bfull table\b", r"\bwinners list\b",
]

GARBLED_MARKERS = ("%20", "\u00c3", "\u00e2\u20ac", "&#x", "\\u0")

# ---------- Cricket-context (kabaddi/hockey/politics reject karne ke liye) ----------
CRICKET_PATTERNS = [
    r"\bcricket\b", r"\bIPL\b", r"\bWPL\b", r"\bODI(s)?\b", r"\bT20I?s?\b",
    r"\bTest (series|match|cricket|debut|squad|century|cap)\b", r"\bTest,?\s*day\b",
    r"\bRanji\b", r"\bDuleep\b", r"\bIrani\b", r"\bVijay Hazare\b",
    r"\bSyed Mushtaq Ali\b", r"\bBCCI\b", r"\bICC\b", r"\bChampions Trophy\b",
    r"\bcentur(y|ies)\b", r"\bwickets?\b", r"\binnings\b", r"\bbowler\b",
    r"\bbatsman\b", r"\ball-rounder\b", r"\bcaptain\b", r"\bcoach\b",
    r"\bsquad\b", r"\bselection\b", r"\bplaying XI\b",
]


def entry_time(entry: dict):
    """RSS item ka published/updated time epoch seconds me (UTC). Na mile to None."""
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return calendar.timegm(st)
            except (TypeError, ValueError):
                continue
    return None


def is_fresh(entry: dict, now: float = None) -> bool:
    """Timestamp missing/invalid => reject. Purani => reject. Sirf 2 ghante ki fresh news."""
    t = entry_time(entry)
    if t is None:
        return False
    now = time.time() if now is None else now
    age = now - t
    return 0 <= age <= FRESH_WINDOW


def is_garbled(text: str) -> bool:
    """Encoded/garbled/unreadable text reject."""
    if not text or not text.strip():
        return True
    if any(marker in text for marker in GARBLED_MARKERS):
        return True
    clean = sum(1 for c in text if c.isalnum() or c.isspace())
    return clean / len(text) < 0.6


def is_india_related(title: str) -> bool:
    t = title or ""
    if any(re.search(p, t, re.I) for p in INDIA_PATTERNS):
        return True
    low = t.lower()
    return any(name.lower() in low for name in PLAYER_NAMES)


def is_cricket_related(title: str) -> bool:
    """India wali har news cricket nahi hoti (kabaddi, hockey, politics...).
    Cricket context ya Indian player ka naam zaroori hai."""
    t = title or ""
    low = t.lower()
    if any(name.lower() in low for name in PLAYER_NAMES):
        return True
    return any(re.search(p, t, re.I) for p in CRICKET_PATTERNS)


def is_rejected(title: str) -> bool:
    t = title or ""
    return any(re.search(p, t, re.I) for p in REJECT_PATTERNS)


def should_accept(entry: dict, now: float = None):
    """Poora filter. Return: (accept: bool, reason: str)."""
    title = strip_source(entry.get("title", ""))
    if is_garbled(title):
        return False, "garbled"
    if not is_fresh(entry, now):
        return False, "stale/missing-timestamp"
    if is_rejected(title):
        return False, "rejected-topic"
    if not is_india_related(title):
        return False, "not-india"
    if not is_cricket_related(title):
        return False, "not-cricket"
    return True, "ok"


# ---------- duplicate detection ----------

def normalize_headline(title: str) -> str:
    """Headline normalization: source suffix, URLs, hashtags, emojis, punctuation sab hatao."""
    t = strip_source(title or "").lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"#\w+", " ", t)          # hashtags decoration hai, news nahi
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def headline_hash(title: str) -> str:
    """Normalized headline ka SHA-1 hash — same news = same hash."""
    return hashlib.sha1(normalize_headline(title).encode("utf-8")).hexdigest()
