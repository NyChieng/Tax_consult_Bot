import json
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import redis
import structlog

from config import settings
from bot.conversation import handle_query
from bot.system_prompt import WELCOME_MESSAGE

logger = structlog.get_logger()

redis_client = None


def get_redis():
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            redis_client.ping()
        except Exception:
            redis_client = None
    return redis_client


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE["en"])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🔍 *MyCukai Assistant - Help*

*What I can answer:*
• Personal income tax rates & brackets
• Tax reliefs and deductions available
• e-Filing procedures and deadlines
• Corporate tax for SMEs and companies
• SST registration and filing
• RPGT on property sales
• Stamp duty calculations
• Withholding tax for foreign payments
• Expatriate tax obligations

*Commands:*
/start - Welcome message
/help - This help message
/lang - Set language preference

*Tips:*
• Ask specific questions for best results
• I cite official LHDN sources
• I support English, BM, and Chinese

*Limitations:*
• I cannot calculate your specific tax
• I cannot file returns for you
• Always verify with LHDN or a tax agent"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🌐 *Language / Bahasa / 语言*

I automatically detect your language.
Just type in your preferred language:

• English → I reply in English
• Bahasa Malaysia → Saya jawab dalam BM
• 中文 → 我会用中文回答

No need to change settings!"""
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    message_text = update.message.text

    if not message_text:
        return

    # Rate limiting
    r = get_redis()
    if r:
        rate_key = f"tg_rate:{user_id}"
        current = r.get(rate_key)
        if current and int(current) >= settings.max_queries_per_hour:
            await update.message.reply_text(
                "⏳ You've reached the hourly limit (30 queries). Please try again later."
            )
            return
        pipe = r.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 3600)
        pipe.execute()

    # Get conversation history from Redis
    history = []
    if r:
        session_key = f"tg_session:{user_id}"
        raw_history = r.lrange(session_key, 0, 9)
        for item in reversed(raw_history):
            try:
                history.append(json.loads(item))
            except json.JSONDecodeError:
                pass

    # Send typing indicator
    await update.message.chat.send_action("typing")

    # Process query
    result = await handle_query(
        user_message=message_text,
        conversation_history=history,
    )

    response = result["response"]

    # Telegram has a 4096 char limit
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(response)

    # Store in session
    if r:
        session_key = f"tg_session:{user_id}"
        entry = json.dumps({"role": "user", "content": message_text})
        r.lpush(session_key, entry)
        assistant_entry = json.dumps({"role": "assistant", "content": response[:500]})
        r.lpush(session_key, assistant_entry)
        r.ltrim(session_key, 0, 19)
        r.expire(session_key, 86400)


def create_telegram_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def setup_commands(app: Application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help information"),
        BotCommand("lang", "Language settings"),
    ]
    await app.bot.set_my_commands(commands)


def run_telegram_bot():
    app = create_telegram_app()
    logger.info("starting_telegram_bot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_telegram_bot()
