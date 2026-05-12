import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from storage import init_db
from handlers import (
    build_onboarding_handler,
    build_profile_handler,
    build_workout_handler,
    build_feedback_handler,
    show_exercise_details,
    cancel,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(build_onboarding_handler())
    app.add_handler(build_profile_handler())
    app.add_handler(build_workout_handler())
    app.add_handler(build_feedback_handler())
    # Global callback handlers (not tied to a ConversationHandler state)
    app.add_handler(CallbackQueryHandler(show_exercise_details, pattern=r"^details_\d+$"))
    app.add_handler(CommandHandler("cancel", cancel))

    logging.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
