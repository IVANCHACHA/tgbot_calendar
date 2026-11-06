"""
calendar_utils.py — чтение и запись событий Apple Calendar через AppleScript
Все изменения синхронизируются с приложением Календарь и iPhone через iCloud.
"""
import subprocess
import datetime
from typing import Optional


def _quote_applescript(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped.replace("\r", "\\r").replace("\n", "\\n") + '"'


def _run_applescript(script: str) -> str:
    """Выполняет AppleScript и возвращает результат."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript ошибка: {result.stderr.strip()}")
    return result.stdout.strip()


def get_events_for_date(target_date: datetime.date) -> list[dict]:
    """
    Возвращает список событий на указанную дату из Apple Calendar.
    Каждое событие: {'title': str, 'start': str, 'end': str, 'calendar': str, 'uid': str}
    """
    year = target_date.year
    month = target_date.month
    day = target_date.day

    script = f"""
    set startOfDay to current date
    set day of startOfDay to 1
    set year of startOfDay to {year}
    set month of startOfDay to {month}
    set day of startOfDay to {day}
    set hours of startOfDay to 0
    set minutes of startOfDay to 0
    set seconds of startOfDay to 0

    set endOfDay to startOfDay + (23 * hours) + (59 * minutes) + 59

    set output to ""
    tell application "Calendar"
        set activeCals to (every calendar whose name does not contain "Праздн" and name does not contain "Holiday" and name does not contain "Siri" and name does not contain "Дни рождения")
        repeat with aCal in activeCals
            set calName to name of aCal
            set eventsOnDay to (every event of aCal whose start date >= startOfDay and start date <= endOfDay)
            repeat with anEvent in eventsOnDay
                set eventTitle to summary of anEvent
                set startTime to start date of anEvent
                set endTime to end date of anEvent
                set eventUID to uid of anEvent
                set output to output & calName & "|" & eventTitle & "|" & (startTime as string) & "|" & (endTime as string) & "|" & eventUID & "\\n"
            end repeat
        end repeat
    end tell
    return output
    """

    try:
        raw = _run_applescript(script)
    except RuntimeError:
        return []

    events = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            events.append({
                "calendar": parts[0].strip(),
                "title": parts[1].strip(),
                "start": parts[2].strip(),
                "end": parts[3].strip(),
                "uid": parts[4].strip(),
            })

    # Сортировка по времени начала
    events.sort(key=lambda e: e["start"])
    return events


def format_events_message(events: list[dict], date: datetime.date) -> str:
    """Форматирует список событий в читаемый текст для Telegram."""
    weekdays_ru = {
        0: "понедельник", 1: "вторник", 2: "среда",
        3: "четверг", 4: "пятница", 5: "суббота", 6: "воскресенье"
    }
    months_ru = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    day_name = weekdays_ru[date.weekday()]
    date_label = f"{date.day} {months_ru[date.month]}, {day_name}"

    if not events:
        return f"📅 *{date_label}*\n\nСобытий нет — свободный день! 🎉"

    lines = [f"📅 *{date_label}*\n"]
    for i, ev in enumerate(events, 1):
        # Парсим время из строки AppleScript (e.g. "Monday, March 9, 2026 at 9:00:00 AM")
        start_time = _parse_applescript_time(ev["start"])
        end_time = _parse_applescript_time(ev["end"])
        lines.append(f"{i}. 🕐 *{start_time}–{end_time}*\n   📌 {ev['title']}\n   📁 {ev['calendar']}")

    return "\n".join(lines)


def add_event(title: str, start_datetime: datetime.datetime,
              end_datetime: Optional[datetime.datetime] = None,
              calendar_name: str = "Календарь") -> bool:
    """Добавляет новое событие в Apple Calendar."""
    if end_datetime is None:
        end_datetime = start_datetime + datetime.timedelta(hours=1)

    sy, smo, sd, sh, smin = start_datetime.year, start_datetime.month, start_datetime.day, start_datetime.hour, start_datetime.minute
    ey, emo, ed, eh, emin = end_datetime.year, end_datetime.month, end_datetime.day, end_datetime.hour, end_datetime.minute
    quoted_title = _quote_applescript(title)

    date_script = f"""
    set tStart to current date
    set day of tStart to 1
    set year of tStart to {sy}
    set month of tStart to {smo}
    set day of tStart to {sd}
    set hours of tStart to {sh}
    set minutes of tStart to {smin}
    set seconds of tStart to 0

    set tEnd to current date
    set day of tEnd to 1
    set year of tEnd to {ey}
    set month of tEnd to {emo}
    set day of tEnd to {ed}
    set hours of tEnd to {eh}
    set minutes of tEnd to {emin}
    set seconds of tEnd to 0
    """

    script = date_script + f"""
    tell application "Calendar"
        set targetCal to calendar {_quote_applescript(calendar_name)}
        make new event at end of events of targetCal with properties {{¬
            summary:{quoted_title}, ¬
            start date:tStart, ¬
            end date:tEnd¬
        }}
    end tell
    """

    try:
        _run_applescript(script)
        return True
    except RuntimeError:
        # Попробуем первый доступный календарь
        script_fallback = date_script + f"""
        tell application "Calendar"
            set targetCal to first calendar
            make new event at end of events of targetCal with properties {{¬
                summary:{quoted_title}, ¬
                start date:tStart, ¬
                end date:tEnd¬
            }}
        end tell
        """
        try:
            _run_applescript(script_fallback)
            return True
        except RuntimeError:
            return False


def delete_event_by_uid(uid: str) -> bool:
    """Удаляет событие по его UID."""
    # Ограничиваем область поиска только событиями за последние/будущие месяцы,
    # чтобы AppleScript не зависал, перебирая всю историю Календаря за 10 лет
    script = f"""
    set d1 to (current date) - (180 * days)
    set d2 to (current date) + (180 * days)

    tell application "Calendar"
        set activeCals to (every calendar whose name does not contain "Праздн" and name does not contain "Holiday" and name does not contain "Siri" and name does not contain "Дни рождения")
        repeat with aCal in activeCals
            set matchingEvents to (every event of aCal whose start date > d1 and start date < d2 and uid = {_quote_applescript(uid)})
            if (count of matchingEvents) > 0 then
                repeat with anEvent in matchingEvents
                    delete anEvent
                end repeat
                return "done"
            end if
        end repeat
    end tell
    """
    try:
        return _run_applescript(script) == "done"
    except RuntimeError:
        return False


def edit_event_title_by_uid(uid: str, new_title: str) -> bool:
    """Изменяет название события по его UID."""
    script = f"""
    tell application "Calendar"
        set activeCals to (every calendar whose name does not contain "Праздн" and name does not contain "Holiday" and name does not contain "Siri" and name does not contain "Дни рождения")
        repeat with aCal in activeCals
            set matchingEvents to (every event of aCal whose uid = {_quote_applescript(uid)})
            repeat with anEvent in matchingEvents
                set summary of anEvent to {_quote_applescript(new_title)}
                return "done"
            end repeat
        end repeat
    end tell
    """
    try:
        return _run_applescript(script) == "done"
    except RuntimeError:
        return False


def get_calendar_names() -> list[str]:
    """Возвращает список имён всех календарей."""
    script = """
    tell application "Calendar"
        set output to ""
        repeat with aCal in calendars
            set output to output & (name of aCal) & "\\n"
        end repeat
        return output
    end tell
    """
    try:
        raw = _run_applescript(script)
        return [line.strip() for line in raw.strip().split("\n") if line.strip()]
    except RuntimeError:
        return []


def _parse_applescript_time(time_str: str) -> str:
    """
    Парсит строку времени из AppleScript и возвращает HH:MM.
    AppleScript возвращает формат вроде "Monday, March 9, 2026 at 9:00:00 AM" (англ)
    Или "вторник, 10 марта 2026 г. в 15:00:00" (русс)
    """
    try:
        if " at " in time_str:
            time_part = time_str.split(" at ")[-1]  # "9:00:00 AM"
            t = datetime.datetime.strptime(time_part.strip(), "%I:%M:%S %p")
            return t.strftime("%H:%M")
        elif " в " in time_str:
            time_part = time_str.split(" в ")[-1].strip()  # "15:00:00"
            return time_part[:5]  # Возвращаем первые 5 символов "15:00"
        return time_str
    except Exception:
        return time_str
