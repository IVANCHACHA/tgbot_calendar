# Голосовой Telegram-бот для Apple Calendar

Личный помощник для macOS. Читает расписание, добавляет и переименовывает события, удаляет выбранное событие после подтверждения и присылает утреннюю сводку. Для быстрого просмотра есть команды `/schedule`, `/tomorrow` и `/calendars`.

Голосовое сообщение преобразуется в текст локально с помощью FFmpeg и faster-whisper. Groq получает текст команды и даты ближайшей недели и возвращает намерение в JSON. Python выбирает обработчик, который обращается к Apple Calendar через AppleScript. Бот принимает сообщения только из одного настроенного личного чата.

## Запуск на macOS

Нужны Python 3.12, FFmpeg в `PATH`, Telegram-бот и ключ Groq. С первого голосового запроса faster-whisper загружает модель `base` и запускает её на CPU.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

В `.env` задай `TELEGRAM_BOT_TOKEN`, числовой `TELEGRAM_CHAT_ID` своего личного чата с ботом и `GROQ_API_KEY`. При необходимости укажи доступную аккаунту модель в `GROQ_MODEL`. Настройки `MORNING_TIME` и `TIMEZONE` задают время утренней сводки. Используй тот же часовой пояс в macOS и Apple Calendar.

```bash
python main.py
```

При первом обращении к календарю разреши macOS доступ к приложению «Календарь». В Telegram отправь `/start` или попробуй запрос «Покажи расписание на завтра».
