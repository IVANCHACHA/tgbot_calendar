"""
scheduler.py — утренняя рассылка через APScheduler
Каждый день в заданное время отправляет приветствие + расписание из Apple Calendar
"""
import logging
import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import MORNING_TIME, TIMEZONE, TELEGRAM_CHAT_ID
from calendar_utils import get_events_for_date, format_events_message

logger = logging.getLogger(__name__)


MORNING_GREETINGS = [
    "☀️ Доброе утро! Новый день — новые возможности!",
    "🌅 Доброе утро! Сегодня будет отличный день!",
    "✨ Доброе утро! Давай сделаем этот день продуктивным!",
    "🌞 Привет! Бодрость и энергия тебе на весь день!",
    "💪 Доброе утро! Ты готов покорять горы? Поехали!",
]

import random


async def send_morning_message(bot, chat_id: int):
    """Отправляет утреннее приветствие + расписание на сегодня."""
    today = datetime.date.today()
    greeting = random.choice(MORNING_GREETINGS)

    events = get_events_for_date(today)
    schedule_text = format_events_message(events, today)

    message = f"{greeting}\n\n{schedule_text}"

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )
        logger.info(f"Утреннее сообщение отправлено в {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки утреннего сообщения: {e}")


def setup_scheduler(bot) -> AsyncIOScheduler:
    """
    Создаёт и настраивает планировщик с утренней задачей.
    Возвращает запущенный планировщик.
    """
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Парсим время из конфига (формат HH:MM)
    try:
        hour, minute = map(int, MORNING_TIME.split(":"))
    except ValueError:
        hour, minute = 8, 0
        logger.warning(f"Не удалось разобрать MORNING_TIME='{MORNING_TIME}', используем 08:00")

    scheduler.add_job(
        send_morning_message,
        "cron",
        hour=hour,
        minute=minute,
        args=[bot, TELEGRAM_CHAT_ID],
        id="morning_message",
        replace_existing=True,
    )

    logger.info(f"Планировщик настроен: утреннее сообщение в {hour:02d}:{minute:02d} ({TIMEZONE})")
    return scheduler
