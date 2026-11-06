"""
main.py — точка входа Telegram AI-агента
Запуск: python main.py
"""
import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, validate_config
from handlers import (
    cmd_start,
    cmd_schedule,
    cmd_tomorrow,
    cmd_calendars,
    handle_text,
    handle_voice,
    handle_callback,
)
from scheduler import setup_scheduler

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def require_owner_chat(update: Update, context):
    chat = update.effective_chat
    if chat is None or chat.type != "private" or chat.id != TELEGRAM_CHAT_ID:
        raise ApplicationHandlerStop


async def post_init(application: Application):
    """Запускается после инициализации приложения."""
    scheduler = setup_scheduler(application.bot)
    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    logger.info(f"Бот запущен! Chat ID: {TELEGRAM_CHAT_ID}")

    # Отправляем сообщение о запуске
    try:
        await application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="🤖 Бот запущен и готов к работе!\nНапиши /start для списка команд.",
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить стартовое сообщение: {e}")


async def post_shutdown(application: Application):
    """Завершение — останавливаем планировщик."""
    scheduler = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Бот остановлен.")


def main():
    # Проверяем конфиг
    errors = validate_config()
    if errors:
        print("❌ ОШИБКИ КОНФИГУРАЦИИ:")
        for err in errors:
            print(f"  • {err}")
        print("\nСкопируй .env.example в .env и заполни значения.")
        sys.exit(1)

    print("🚀 Запуск бота...")

    # Создаём приложение
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(TypeHandler(Update, require_owner_chat), group=-1)

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("tomorrow", cmd_tomorrow))
    app.add_handler(CommandHandler("calendars", cmd_calendars))

    # Голосовые сообщения
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Текстовые сообщения (кроме команд)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Inline кнопки
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск (polling)
    print(f"✅ Бот работает. Отправь /start в Telegram (chat_id: {TELEGRAM_CHAT_ID})")
    print("   Нажми Ctrl+C для остановки.\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
