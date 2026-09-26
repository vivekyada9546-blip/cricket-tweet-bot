"""
Cricket Tweet Draft Bot (interactive) — 100% free
================================================
कोई भी text / forwarded news इस बॉट को भेजो — यह tweet-ready draft
(280 characters + hashtags) बनाकर एक Copy button के साथ वापस भेजता है।
Copy करके X पर paste कर दो — tweet पोस्ट। कोई X API नहीं, कोई पैसा नहीं।

चलाने के लिए: .env में BOT_TOKEN और ADMIN_IDS भरो, फिर:
    python bot.py
"""

import logging
import os
import re

from dotenv import load_dotenv
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from draft import cap_for_copy, make_styled_tweet, smart_tags

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in re.findall(r"\d+", os.getenv("ADMIN_IDS", ""))}
DEFAULT_TAGS = os.getenv("HASHTAGS", "#TeamIndia #IndianCricket").strip() or "#TeamIndia #IndianCricket"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("bot")

WELCOME = (
    "Cricket Tweet Draft Bot\n\n"
    "- कोई भी news text भेजो (या forward करो) — tweet-ready draft Copy button के साथ मिलेगा।\n"
    "- /post <text> — इसी से भी draft बन सकता है।\n"
    "- /tags #A #B — अपने hashtags सेट करो (खाली /tags = default पर वापस)।\n"
    "- Draft copy करके X पर paste करो — बस, tweet पोस्ट।"
)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def deny(update: Update) -> None:
    await update.effective_message.reply_text(
        "ये personal bot है — सिर्फ owner इस्तेमाल कर सकता है।\n"
        f"(आपकी Telegram ID: {update.effective_user.id})"
    )


def chat_tags(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> str:
    return context.bot_data.setdefault("tags", {}).get(chat_id, DEFAULT_TAGS)


def build_reply(draft: str):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Copy tweet", copy_text=CopyTextButton(text=cap_for_copy(draft)))],
         [InlineKeyboardButton("Without hashtags", callback_data="nohash")]]
    )
    header = f"Tweet ready — {len(draft)}/280 characters:\n\n{draft}"
    return header, keyboard


async def send_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    tags = smart_tags(text, chat_tags(context, update.effective_chat.id))
    draft = make_styled_tweet(text, tags)
    header, keyboard = build_reply(draft)
    # "nohash" button के लिए original text याद रखो
    context.bot_data.setdefault("last", {})[update.effective_chat.id] = text
    await update.effective_message.reply_text(
        header, reply_markup=keyboard, disable_web_page_preview=True
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not ADMIN_IDS:
        await update.effective_message.reply_text(
            f"Setup अधूरा है। आपकी Telegram ID: {uid}\n"
            "इसे .env फाइल के ADMIN_IDS में डालकर bot restart करो।"
        )
        return
    if not is_admin(uid):
        await deny(update)
        return
    await update.effective_message.reply_text(WELCOME)


async def cmd_tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await deny(update)
        return
    chat_id = update.effective_chat.id
    arg = " ".join(context.args).strip()
    if not arg:
        context.bot_data.setdefault("tags", {}).pop(chat_id, None)
        await update.effective_message.reply_text(f"Custom hashtags हटाए। अब default: {DEFAULT_TAGS}")
    else:
        context.bot_data.setdefault("tags", {})[chat_id] = arg
        await update.effective_message.reply_text(f"Hashtags सेट हुए: {arg}")


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await deny(update)
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("Usage: /post यहाँ tweet का text लिखो")
        return
    await send_draft(update, context, text)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await deny(update)
        return
    await send_draft(update, context, update.effective_message.text)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return
    last_text = context.bot_data.get("last", {}).get(query.message.chat_id)
    await query.answer()
    if not last_text:
        return
    draft = make_styled_tweet(last_text, "")
    header, keyboard = build_reply(draft)
    await query.message.reply_text(
        header, reply_markup=keyboard, disable_web_page_preview=True
    )


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN नहीं मिला — .env फाइल भरो।")
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS खाली है — पहली बार /start दबाने पर बॉट आपकी ID बता देगा।")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("tags", cmd_tags))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_button, pattern="^nohash$"))

    log.info("Bot चालू हो रहा है (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
