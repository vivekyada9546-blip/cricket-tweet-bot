# Cricket Tweet Draft Bot (100% Free)

Telegram bot jo cricket news ko **tweet-ready draft** bana kar deta hai —
ek Copy button ke saath. Aap use copy karke X (Twitter) par paste kar do.
**Koi X API nahi, koi paisa nahi, koi ban ka risk nahi.**

## Yeh kya karta hai

1. **News khud dhoondh kar laata hai** — har 2 ghante Google News se latest
   cricket news utha kar aapke Telegram par bhejta hai, Copy button ke saath.
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

## Setup

1. Telegram me **@BotFather** ko `/newbot` bhejo -> token milega.
2. **@userinfobot** se apni Telegram ID nikalo.
3. Ye repo fork/copy karke files upload karo.
4. Repo me: **Settings -> Secrets and variables -> Actions**:
   - `BOT_TOKEN` = bot ka token
   - `CHAT_ID` = aapki ID (ya channel ka @username)
5. Actions tab -> "Cricket news" -> **Run workflow**.

## News apne CHANNEL me bhejni hai?

1. Channel me bot ko **admin** banao (Administrators -> Add admin).
2. `CHAT_ID` secret me channel ka username likho, jaise `@my_cricket_channel`.

(Personal chat me chahiye to `CHAT_ID` me apni hi ID rakho.)

## (Optional) PC par interactive bot

```bash
pip install -r requirements.txt
cp .env.example .env     # BOT_TOKEN aur ADMIN_IDS bharo
python bot.py
```

- Koi bhi text bhejo -> tweet draft + Copy button.
- `/tags #IPL #TeamIndia` se apne hashtags set karo.

## News sources

Default feeds **sirf Indian cricket** — Team India, playing XI, IPL aur
Indian domestic (Ranji / Duleep / Irani). `RSS_URLS` env se badal sakte ho.

## Zaroori baatein

- `.env` kabhi GitHub par commit mat karna — token wahi hai.
- Yeh tweet **post** nahi karta, sirf **draft + Copy button** deta hai —
  isliye X ke rules se koi takraav nahi.
