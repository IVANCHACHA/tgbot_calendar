"""
voice_handler.py — обработка голосовых сообщений через faster-whisper (локально, бесплатно)
Конвертация OGG→WAV через ffmpeg, транскрипция через faster-whisper
"""
import os
import asyncio
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)

# Глобальный объект модели (загружается один раз)
_whisper_model = None


def _load_whisper(model_name: str = "base"):
    """Ленивая загрузка модели faster-whisper (скачивается при первом вызове ~150 МБ)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info(f"Загружаю модель faster-whisper '{model_name}'...")
        # device="cpu", compute_type="int8" — работает без GPU
        _whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
        logger.info("faster-whisper загружен!")
    return _whisper_model


async def transcribe_voice(ogg_bytes: bytes, model_name: str = "base") -> str:
    """
    Принимает байты OGG-файла (голосовое из Telegram),
    конвертирует в WAV и транскрибирует через faster-whisper.
    Возвращает распознанный текст.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, ogg_bytes, model_name)


def _transcribe_sync(ogg_bytes: bytes, model_name: str) -> str:
    """Синхронная транскрипция (запускается в отдельном потоке)."""
    os.makedirs("voice_tmp", exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".ogg", dir="voice_tmp", delete=False) as ogg_f:
        ogg_f.write(ogg_bytes)
        ogg_path = ogg_f.name

    wav_path = ogg_path.replace(".ogg", ".wav")

    try:
        # Конвертация OGG → WAV через ffmpeg
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.error(f"ffmpeg ошибка: {result.stderr.decode()}")
            return ""

        # Транскрипция через faster-whisper
        model = _load_whisper(model_name)
        segments, info = model.transcribe(wav_path, language="ru", beam_size=5)

        text = " ".join(segment.text for segment in segments).strip()
        return text

    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        return ""
    finally:
        for path in [ogg_path, wav_path]:
            if os.path.exists(path):
                os.remove(path)
