"""
Синтез речи (TTS) для Аники.
Использует Silero TTS v4 для русского языка — полностью офлайн.
"""

import os
import sys
import io
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_tts_lock = threading.Lock()
_model = None
_model_loaded = False
_sample_rate = 24000


def _load_silero_model():
    """Загрузить модель Silero TTS."""
    global _model, _model_loaded, _sample_rate
    try:
        import torch
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "models")
        os.makedirs(models_dir, exist_ok=True)

        model_path = os.path.join(models_dir, "silero_tts_ru.pt")

        if os.path.exists(model_path):
            model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
        else:
            logger.info("Загружаю Silero TTS модель...")
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language="ru",
                speaker="v4_ru",
            )
            torch.save(model, model_path)

        device = torch.device("cpu")
        model.to(device)
        _model = model
        _model_loaded = True
        logger.info("Silero TTS модель загружена")
        return True
    except Exception as e:
        logger.warning(f"Не удалось загрузить Silero TTS: {e}. Переключаюсь на pyttsx3.")
        return False


def _speak_silero(text: str, speaker: str = "xenia") -> bool:
    """Воспроизвести речь через Silero TTS."""
    global _model, _sample_rate
    try:
        import torch
        import sounddevice as sd

        with _tts_lock:
            if not _model_loaded:
                if not _load_silero_model():
                    return False

            audio = _model.apply_tts(
                text=text,
                speaker=speaker,
                sample_rate=_sample_rate,
                put_accent=True,
                put_yo=True
            )

            audio_np = audio.numpy()
            sd.play(audio_np, samplerate=_sample_rate)
            sd.wait()
            return True
    except Exception as e:
        logger.error(f"Ошибка Silero TTS: {e}")
        return False


def _speak_pyttsx3(text: str) -> bool:
    """Запасной TTS через pyttsx3."""
    try:
        import pyttsx3
        engine = pyttsx3.init()

        voices = engine.getProperty("voices")
        russian_voice = None
        for voice in voices:
            if "russian" in voice.name.lower() or "ru" in voice.id.lower():
                russian_voice = voice.id
                break

        if russian_voice:
            engine.setProperty("voice", russian_voice)

        engine.setProperty("rate", 175)
        engine.setProperty("volume", 0.9)
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        logger.error(f"Ошибка pyttsx3: {e}")
        return False


_tts_backend = None


def get_tts_backend() -> str:
    """Определить лучший доступный TTS-бэкенд."""
    global _tts_backend
    if _tts_backend:
        return _tts_backend

    try:
        import torch
        import sounddevice
        _tts_backend = "silero"
        return _tts_backend
    except ImportError:
        pass

    try:
        import pyttsx3
        _tts_backend = "pyttsx3"
        return _tts_backend
    except ImportError:
        pass

    _tts_backend = "none"
    return _tts_backend


def speak(text: str, blocking: bool = True) -> bool:
    """
    Воспроизвести текст голосом.

    Args:
        text: Текст для произношения
        blocking: Ждать завершения воспроизведения

    Returns:
        True если успешно
    """
    if not text or not text.strip():
        return False

    text = _preprocess_text(text)

    def _do_speak():
        backend = get_tts_backend()
        if backend == "silero":
            success = _speak_silero(text)
            if not success:
                _speak_pyttsx3(text)
        elif backend == "pyttsx3":
            _speak_pyttsx3(text)
        else:
            logger.warning("Нет доступного TTS-бэкенда")

    if blocking:
        _do_speak()
        return True
    else:
        thread = threading.Thread(target=_do_speak, daemon=True)
        thread.start()
        return True


def _preprocess_text(text: str) -> str:
    """Предобработка текста перед TTS."""
    import re
    text = re.sub(r"[*_~`#]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"https?://\S+", "ссылка", text)
    if len(text) > 500:
        text = text[:500] + "..."
    return text


def preload():
    """Предзагрузить TTS в фоне."""
    backend = get_tts_backend()
    if backend == "silero":
        threading.Thread(target=_load_silero_model, daemon=True).start()
    logger.info(f"TTS бэкенд: {backend}")
