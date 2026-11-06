"""
config.py — загрузка конфигурации из .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
try:
    TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", ""))
except ValueError:
    TELEGRAM_CHAT_ID = 0

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Расписание утреннего сообщения (формат HH:MM)
MORNING_TIME: str = os.getenv("MORNING_TIME", "08:00")

# Часовой пояс
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

# Whisper модель (tiny/base/small/medium) — base хороший баланс скорости и качества
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

def validate_config():
    """Проверяет, что обязательные поля заполнены."""
    errors = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        errors.append("TELEGRAM_BOT_TOKEN не задан в .env")
    if TELEGRAM_CHAT_ID <= 0:
        errors.append("TELEGRAM_CHAT_ID должен быть положительным ID личного чата")
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        errors.append("GROQ_API_KEY не задан в .env")
    return errors
