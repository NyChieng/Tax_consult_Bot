import json
import asyncio
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import structlog

from config import settings
from bot.conversation import handle_query
from bot.system_prompt import WELCOME_MESSAGE

logger = structlog.get_logger()

# Simple in-memory session (works without Redis)
sessions: dict[str, list[dict]] = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE["en"], parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """Just ask me anything about Malaysian tax — like texting a friend who knows this stuff.

*Some things people ask me:*
• "How much tax do I pay on 80k salary?"
• "Can I claim my laptop?"
• "When's the deadline to file?"
• "Do I need to register for SST?"
• "Selling my house — any tax?"

I speak English, BM, and 中文.

_I'm a reference tool, not a tax agent — for personal calculations or filing, see a professional ya._"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """Just type in whatever language you prefer — I'll match you automatically.

🇬🇧 English → I reply English
🇲🇾 BM → Saya jawab BM
🇨🇳 中文 → 我用中文回答"""
    await update.message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    message_text = update.message.text

    if not message_text:
        return

    # Get conversation history (in-memory, last 6 messages)
    history = sessions.get(user_id, [])

    # Show typing
    await update.message.chat.send_action("typing")

    # Process query
    result = await handle_query(
        user_message=message_text,
        conversation_history=history,
        user_id=user_id,
    )

    response = result["response"]

    # Send reply (handle Telegram 4096 char limit)
    if len(response) > 4000:
        parts = [response[i:i + 4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode="Markdown")
    else:
        try:
            await update.message.reply_text(response, parse_mode="Markdown")
        except Exception:
            # Markdown parse error fallback
            await update.message.reply_text(response)

    # Store in session (keep last 6 exchanges)
    if user_id not in sessions:
        sessions[user_id] = []
    sessions[user_id].append({"role": "user", "content": message_text})
    sessions[user_id].append({"role": "assistant", "content": response[:500]})
    sessions[user_id] = sessions[user_id][-12:]  # 6 exchanges


async def run_online_learner_background():
    """Background task: learn from online sources every 4 hours."""
    await asyncio.sleep(30)  # Wait 30s after startup
    try:
        from agent.online_learner import OnlineLearner
        learner = OnlineLearner()
        while True:
            try:
                facts = await learner.learn_cycle()
                if facts:
                    logger.info("learned_new_facts", count=len(facts))
            except Exception as e:
                logger.warning("online_learning_error", error=str(e))
            await asyncio.sleep(4 * 3600)  # Every 4 hours
    except Exception as e:
        logger.warning("online_learner_init_error", error=str(e))


def create_telegram_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start online learner as background task
    app.post_init = _post_init

    return app


async def _post_init(application: Application):
    """Start background tasks after bot initializes."""
    asyncio.create_task(run_online_learner_background())
    logger.info("background_learner_started")


def run_telegram_bot():
    app = create_telegram_app()
    logger.info("starting_telegram_bot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_telegram_bot()
