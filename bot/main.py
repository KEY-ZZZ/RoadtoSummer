import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from config import TELEGRAM_TOKEN
from storage import init_db
from handlers import build_conversation_handler, start, cancel

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(build_conversation_handler())

    logging.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
