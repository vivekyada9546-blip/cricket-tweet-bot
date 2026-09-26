# Cricket Tweet Draft Bot (100% Free)

Telegram bot jo cricket news ko **tweet-ready draft** bana kar deta hai —
ek Copy button ke saath. Aap use copy karke X (Twitter) par paste kar do.
**Koi X API nahi, koi paisa nahi, koi ban ka risk nahi.**

## Yeh kya karta hai

1. **News khud dhoondh kar laata hai** — har 2 ghante ESPNcricinfo + Google News
   se **sirf Indian cricket** ki **fresh (2 ghante ki)** news bhejta hai.
   Duplicates, purani, irrelevant aur non-cricket news filter ho jaati hai.
   Jahan image milegi wahan photo ke saath post hoti hai.
2. **Aapka bheja text bhi tweet bana deta hai** — bot ko koi bhi text ya
   forwarded news bhejo, 280-character draft (hashtags ke saath) turant
   milega.
3. Aap draft check karo -> Copy dabao -> X par paste karke post.
   (Post karne se pehle aap khud dekh lete ho ki kya ja raha hai.)

## Total cost: 0 rupaye

| Cheez | Cost |
|---|---|
| Telegram bot token (@BotFather) | Free |
| GitHub Actions (public repo) | Free |
| Google News RSS | Free |
| X API | Is design me zaroorat hi nahi |

## Setup — 15 minute ka kaam

### Step 1: Bot banao (2 minute)

1. Telegram me **@BotFather** kholo -> `/newbot` bhejo.
2. Bot ka naam poochega (jaise `My Cricket Bot`) -> likho.
3. Username poochega (jaise `cricket_tweets_bot` — end me `bot` hona chahiye) -> likho.
4. **Token** milega — jaise `1234567890:AAHf3...` — copy karke rakh lo.
   Yeh secret hai, kisi ko mat dena.

### Step 2: Apni Telegram ID nikalo

**@userinfobot** ko `/start` bhejo — wo aapki numeric ID bata degi
(jaise `123456789`). Yaad rakhna — yahi ID har jagah lagegi.

### Step 3: Yeh code GitHub par daalo

1. GitHub par naya repo banao (Public rakhna better hai — Actions free).
2. Ye saari files upload karo: `bot.py`, `fetch_news.py`, `draft.py`,
   `filters.py`, `tests/`, `requirements.txt`, `.env.example`, `.gitignore`,
   aur `.github` folder.

### Step 4: Secrets bharo

Repo me: **Settings -> Secrets and variables -> Actions -> New repository secret**

- `BOT_TOKEN` = Step 1 wala token
- `CHAT_ID` = Step 2 wali aapki ID (ya channel ka @username)

### Step 5: Chalu karo

Repo me **Actions** tab kholo -> "Cricket news" workflow me
**Run workflow** button dabao. Done! Telegram par news drafts aane
lgegen, har draft ke saath **Copy tweet** button hoga.

Bas — ab har 2 ghante khud chalta rahega. (`.github/workflows/news.yml`
me `cron: "0 */2 * * *"` line se timing badal sakte ho.)

## News apne CHANNEL me bhejni hai? (personal chat ki jagah)

1. Channel me bot ko **admin** banao (Administrators -> Add admin).
2. `CHAT_ID` secret me channel ka username likho, jaise `@my_cricket_channel`.

(Personal chat me chahiye to `CHAT_ID` me apni hi ID rakho.)

## (Optional) PC / server par interactive bot chalana

```bash
pip install -r requirements.txt
cp .env.example .env     # .env kholkar BOT_TOKEN aur ADMIN_IDS bharo
python bot.py
```

- Bot ko `/start` bhejo — khud kaam samjha dega.
- Koi bhi text bhejo -> tweet draft + Copy button.
- `/tags #IPL #TeamIndia` se apne hashtags set karo.

## Apni news source badalna

ESPNcricinfo (primary) + Google News India queries. Har item par lagte hain:
2-ghante freshness (actual RSS timestamp), Indian cricket relevance,
junk/garbled reject, aur duplicate detection (headline hash).
`RSS_URLS` env se sources badal sakte ho, jaise:

```
https://news.google.com/rss/search?q=IPL+when:1d&hl=en-IN&gl=IN&ceid=IN:en
https://news.google.com/rss/search?q=cricket+score&hl=en-IN&gl=IN&ceid=IN:en
```

## Zaroori baatein

- **.env kabhi GitHub par commit mat karna** — token wahi hai. (Isliye
  `.gitignore` me daal diya gaya hai; GitHub par sirf Secrets me bharo.)
- Bot sirf aapke liye hai — doosri ID se use karne par mana kar dega.
- Yeh tweet **post** nahi karta, sirf **draft + Copy button** deta hai —
  isliye X ke rules se koi takraav nahi aur account kabhi risk me nahi.

## Tests

```bash
python -m unittest discover -s tests -v
python -m py_compile bot.py fetch_news.py draft.py filters.py
```

CI (Actions) me bhi yehi tests har run se pehle chalte hain.
