"""
handlers.py — обработчики команд и сообщений Telegram-бота

Команды:
  /start       — приветствие и список команд
  /schedule    — расписание на сегодня
  /tomorrow    — расписание на завтра
  /calendars   — список доступных календарей

Текстовые сообщения: обрабатываются AI (Groq) → выполняется действие
Голосовые сообщения: Whisper → текст → AI → действие
"""
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import calendar_utils as cal
from ai_handler import parse_intent, parse_date_from_intent, parse_datetime_from_intent
from voice_handler import transcribe_voice
from config import WHISPER_MODEL

logger = logging.getLogger(__name__)

# Временное хранилище событий для удаления (в памяти, на сессию)
_last_events_cache: dict[int, list[dict]] = {}


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Привет! Я твой AI-помощник для Calendar.*\n\n"
        "Я умею:\n"
        "• Присылать расписание из Apple Calendar\n"
        "• Добавлять, изменять и удалять события\n"
        "• Понимать голосовые сообщения 🎙️\n"
        "• Присылать расписание каждое утро ☀️\n\n"
        "*Команды:*\n"
        "/schedule — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/calendars — список календарей\n\n"
        "Или просто напиши мне что нужно сделать, например:\n"
        "_«Добавь встречу завтра в 15:00»_\n"
        "_«Покажи расписание на среду»_\n"
        "_«Удали обед»_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ──────────────────────────────────────────────
# /schedule
# ──────────────────────────────────────────────
async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    await _send_schedule(update, today)


# ──────────────────────────────────────────────
# /tomorrow
# ──────────────────────────────────────────────
async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    await _send_schedule(update, tomorrow)


# ──────────────────────────────────────────────
# /calendars
# ──────────────────────────────────────────────
async def cmd_calendars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = cal.get_calendar_names()
    if names:
        text = "📁 *Твои календари:*\n" + "\n".join(f"• {n}" for n in names)
    else:
        text = "❌ Не удалось получить список календарей.\nУбедись, что приложение Календарь открыто."
    await update.message.reply_text(text, parse_mode="Markdown")


# ──────────────────────────────────────────────
# Текстовые сообщения (AI)
# ──────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # Пропускаем команды
    if user_text.startswith("/"):
        return

    await update.message.reply_text("🤔 Обрабатываю...")

    intent = await parse_intent(user_text)
    await _execute_intent(update, intent, chat_id)


# ──────────────────────────────────────────────
# Голосовые сообщения
# ──────────────────────────────────────────────
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🎙️ Распознаю голос...")

    # Скачиваем голосовое сообщение
    voice = update.message.voice
    voice_file = await context.bot.get_file(voice.file_id)
    ogg_bytes = await voice_file.download_as_bytearray()

    # Транскрибируем
    text = await transcribe_voice(bytes(ogg_bytes), model_name=WHISPER_MODEL)

    if not text:
        await update.message.reply_text(
            "❌ Не смог распознать голос. Попробуй говорить чётче или используй текст."
        )
        return

    await update.message.reply_text(f"📝 Распознал: _{text}_", parse_mode="Markdown")

    # Определяем намерение и выполняем
    intent = await parse_intent(text)
    await _execute_intent(update, intent, chat_id)


# ──────────────────────────────────────────────
# Inline кнопки (для удаления событий)
# ──────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # формат: "delete:<uid>" или "cancel"

    if data == "cancel":
        await query.edit_message_text("❌ Отменено.")
        return

    if data.startswith("delete:"):
        uid = data[len("delete:"):]
        success = cal.delete_event_by_uid(uid)
        if success:
            await query.edit_message_text("✅ Событие удалено из Calendar.")
        else:
            await query.edit_message_text("❌ Не удалось удалить событие.")


# ──────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────
async def _send_schedule(update: Update, date: datetime.date):
    """Получает и отправляет расписание на указанную дату."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔄 Получаю расписание...")

    events = cal.get_events_for_date(date)
    _last_events_cache[chat_id] = events  # Сохраняем для возможного удаления

    text = cal.format_events_message(events, date)
    await update.message.reply_text(text, parse_mode="Markdown")


async def _execute_intent(update: Update, intent: dict, chat_id: int):
    """Выполняет действие на основе распознанного намерения."""
    action = intent.get("action", "unknown")

    # ── VIEW ──
    if action == "view":
        date = parse_date_from_intent(intent)
        events = cal.get_events_for_date(date)
        _last_events_cache[chat_id] = events
        text = cal.format_events_message(events, date)
        await update.message.reply_text(text, parse_mode="Markdown")

    # ── ADD ──
    elif action == "add":
        title = intent.get("title", "Событие")
        start_dt, end_dt = parse_datetime_from_intent(intent)

        success = cal.add_event(title, start_dt, end_dt)
        if success:
            start_str = start_dt.strftime("%d.%m.%Y в %H:%M")
            await update.message.reply_text(
                f"✅ Добавлено: *{title}*\n📅 {start_str}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Не удалось добавить событие в Calendar.")

    # ── DELETE ──
    elif action == "delete":
        keyword = intent.get("keyword", "").lower()

        # Если ИИ передал дату, используем её, иначе ищем сегодня и завтра
        if "date" in intent:
            target_date = parse_date_from_intent(intent)
            events = cal.get_events_for_date(target_date)
        else:
            today = datetime.date.today()
            tomorrow = today + datetime.timedelta(days=1)
            events = cal.get_events_for_date(today) + cal.get_events_for_date(tomorrow)

        # Фильтруем события
        matches = []
        start_time_str = intent.get("start_time")

        for e in events:
            # Если есть ключевое слово, фильтруем по нему
            if keyword and keyword not in e["title"].lower():
                continue

            # Если ключевого слова нет, но есть время, фильтруем по времени
            if not keyword and start_time_str:
                if start_time_str not in str(e.get("start") or ""):
                    continue

            # Если нет ни слова, ни времени (аномалия), пропускаем пустые совпадения
            if not keyword and not start_time_str:
                continue

            matches.append(e)

        if not matches:
            if start_time_str:
                await update.message.reply_text(f"❓ Не нашёл событие в {start_time_str}.")
            else:
                await update.message.reply_text(f"❓ Не нашёл событие с «{keyword}».")
            return

        if len(matches) == 1:
            ev = matches[0]
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"🗑 Удалить «{ev['title']}»", callback_data=f"delete:{ev['uid']}"),
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel")
                ]
            ])
            start_fmt = ev['start'].strftime('%d.%m.%Y в %H:%M') if isinstance(ev['start'], datetime.datetime) else str(ev['start'])
            await update.message.reply_text(
                f"Удалить это событие?\n*{ev['title']}* ({start_fmt})",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            # Несколько совпадений
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🗑 {e['title']}", callback_data=f"delete:{e['uid']}")]
                for e in matches
            ] + [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
            await update.message.reply_text(
                "Нашёл несколько событий. Какое удалить?",
                reply_markup=keyboard
            )

    # ── EDIT ──
    elif action == "edit":
        keyword = (intent.get("keyword") or "").strip().lower()
        new_title = (intent.get("new_title") or "").strip()
        if not keyword or not new_title:
            await update.message.reply_text("Укажи текущее и новое название события.")
            return
        events = cal.get_events_for_date(parse_date_from_intent(intent))

        matches = [e for e in events if keyword in e["title"].lower()]

        if not matches:
            await update.message.reply_text(
                f"❓ Не нашёл событие с «{keyword}»."
            )
            return
        if len(matches) > 1:
            await update.message.reply_text("Нашёл несколько событий. Укажи более точное название.")
            return

        ev = matches[0]
        success = cal.edit_event_title_by_uid(ev["uid"], new_title)
        if success:
            await update.message.reply_text(
                f"✅ Переименовано:\n«{ev['title']}» → «{new_title}»"
            )
        else:
            await update.message.reply_text("❌ Не удалось изменить событие.")

    # ── UNKNOWN ──
    else:
        reply = intent.get("reply", "Не понял запрос. Попробуй переформулировать.")
        await update.message.reply_text(reply)
