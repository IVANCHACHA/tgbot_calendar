"""Определение намерения пользователя через Groq."""
import json
import logging
import datetime
import re
from typing import Optional
from groq import AsyncGroq

from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_client = None


SYSTEM_PROMPT = """Ты — AI-ассистент для управления Apple Calendar через Telegram-бот.
Текущее время: {now}
Календарь на ближайшие дни:
{calendar_context}

Твоя задача — распознать намерение пользователя из его сообщения и вернуть JSON.

Форматы ответа (строго JSON, без markdown):

1. Просмотр расписания:
{{"action": "view", "date": "YYYY-MM-DD"}}

2. Добавление события:
{{"action": "add", "title": "название", "date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM"}}

3. Удаление события:
{{"action": "delete", "keyword": "ключевое слово", "date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM"}}

4. Редактирование события:
{{"action": "edit", "keyword": "старое название", "new_title": "новое название", "date": "YYYY-MM-DD"}}

5. Непонятный запрос или массовое удаление:
{{"action": "unknown", "reply": "ответь пользователю на русском"}}

Правила:
- Обязательно указывай "date", если пользователь говорит про день ("на завтра", "во вторник", "сегодня", "в среду").
- Используй даты из "Календарь на ближайшие дни", чтобы точно определять дни недели.
- Если день не указан явно, используй дату "Сегодня".
- Если время не указано для добавления — ставь start_time 12:00, end_time 13:00
- Отвечай ТОЛЬКО чистым JSON и без лишних слов"""


async def parse_intent(user_text: str) -> dict:
    """
    Отправляет текст в Groq и возвращает разобранное намерение.
    Возвращает dict с полем 'action'.
    """
    now = datetime.datetime.now()
    today = now.date()

    ru_weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    calendar_lines = []
    calendar_lines.append(f"- Сегодня ({ru_weekdays[today.weekday()]}): {today.isoformat()}")
    calendar_lines.append(f"- Завтра ({ru_weekdays[(today.weekday() + 1) % 7]}): {(today + datetime.timedelta(days=1)).isoformat()}")
    for i in range(2, 7):
        future_date = today + datetime.timedelta(days=i)
        calendar_lines.append(f"- {ru_weekdays[future_date.weekday()]}: {future_date.isoformat()}")

    system = SYSTEM_PROMPT.format(
        now=now.strftime("%H:%M"),
        calendar_context="\n".join(calendar_lines),
    )

    global _client
    try:
        if _client is None:
            _client = AsyncGroq(api_key=GROQ_API_KEY)
        response = await _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            temperature=0.1,
            max_completion_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()

        # Убираем markdown-обёртку если есть
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        intent = json.loads(raw)
        if not isinstance(intent, dict):
            raise ValueError("Expected an intent object")
        return {key: value for key, value in intent.items() if isinstance(value, str)}

    except ValueError:
        logger.warning("Groq returned an invalid intent")
        return {"action": "unknown", "reply": "Не смог разобрать ответ AI. Попробуй переформулировать."}
    except Exception as e:
        logger.error("Groq request failed (%s)", type(e).__name__)
        return {"action": "unknown", "reply": "Не удалось обработать запрос через Groq."}


def parse_date_from_intent(intent: dict) -> Optional[datetime.date]:
    """Парсит дату из intent в объект datetime.date."""
    date_str = intent.get("date")
    if not date_str:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return datetime.date.today()


def parse_datetime_from_intent(intent: dict) -> tuple[datetime.datetime, datetime.datetime]:
    """Возвращает (start_datetime, end_datetime) из intent."""
    date = parse_date_from_intent(intent)
    start_time_str = intent.get("start_time", "12:00")
    end_time_str = intent.get("end_time", "13:00")

    def parse_time(t: str) -> datetime.time:
        try:
            return datetime.datetime.strptime(t, "%H:%M").time()
        except (TypeError, ValueError):
            return datetime.time(12, 0)

    start_t = parse_time(start_time_str)
    end_t = parse_time(end_time_str)

    start_dt = datetime.datetime.combine(date, start_t)
    end_dt = datetime.datetime.combine(date, end_t)
    if end_dt <= start_dt:
        end_dt = start_dt + datetime.timedelta(hours=1)

    return start_dt, end_dt
