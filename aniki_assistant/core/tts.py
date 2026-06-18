"""
Синтез речи (TTS) для Аники.
Silero TTS v4 — мужской голос (aidar/eugene), полностью офлайн.
Fallback: pyttsx3 с Windows SAPI.
"""

import os
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_tts_lock = threading.Lock()
_model = None
_model_loaded = False
_sample_rate = 24000

# Мужские голоса Silero для русского: aidar, eugene
# aidar — глубокий, eugene — чуть мягче
SILERO_SPEAKER = "aidar"
SILERO_LANG = "ru"
SILERO_MODEL_ID = "v4_ru"


def _load_silero_model() -> bool:
    """Загрузить модель Silero TTS (мужской голос)."""
    global _model, _model_loaded, _sample_rate
    try:
        import torch
        models_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "models"
        )
        os.makedirs(models_dir, exist_ok=True)
        model_path = os.path.join(models_dir, f"silero_tts_{SILERO_MODEL_ID}.pt")

        if os.path.exists(model_path):
            try:
                model = torch.package.PackageImporter(model_path).load_pickle(
                    "tts_models", "model"
                )
                logger.info("Silero TTS загружен из кэша")
            except Exception:
                os.remove(model_path)
                return _load_silero_model()
        else:
            logger.info("Загружаю Silero TTS v4 ru (мужской голос)...")
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language=SILERO_LANG,
                speaker=SILERO_MODEL_ID,
                verbose=False,
            )
            torch.save(model, model_path)

        device = torch.device("cpu")
        model.to(device)
        _model = model
        _model_loaded = True
        _sample_rate = 24000
        logger.info(f"Silero TTS готов (голос: {SILERO_SPEAKER})")
        return True
    except Exception as e:
        logger.warning(f"Silero TTS недоступен: {e}")
        return False


def _speak_silero(text: str) -> bool:
    """Воспроизвести речь через Silero TTS (мужской голос aidar)."""
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
                speaker=SILERO_SPEAKER,
                sample_rate=_sample_rate,
                put_accent=True,
                put_yo=True,
            )
            audio_np = audio.numpy()
            sd.play(audio_np, samplerate=_sample_rate)
            sd.wait()
            return True
    except Exception as e:
        logger.error(f"Ошибка Silero TTS: {e}")
        return False


def _speak_pyttsx3(text: str) -> bool:
    """Fallback TTS через pyttsx3 (Windows SAPI)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        # Предпочитаем мужской русский голос
        chosen = None
        for v in voices:
            name_low = v.name.lower()
            id_low = v.id.lower()
            is_ru = "russian" in name_low or "ru" in id_low or "pavel" in name_low
            is_male = "pavel" in name_low or "male" in name_low or "man" in name_low
            if is_ru and is_male:
                chosen = v.id
                break
        # Если мужского нет — берём любой русский
        if not chosen:
            for v in voices:
                if "russian" in v.name.lower() or "ru" in v.id.lower():
                    chosen = v.id
                    break
        if chosen:
            engine.setProperty("voice", chosen)
        # Немного замедляем для естественности
        engine.setProperty("rate", 160)
        engine.setProperty("volume", 0.95)
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        logger.error(f"Ошибка pyttsx3: {e}")
        return False


_tts_backend: Optional[str] = None


def get_tts_backend() -> str:
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
    Воспроизвести текст голосом Аники (мужской).
    blocking=False — запускает в фоне.
    """
    if not text or not text.strip():
        return False

    text = _preprocess_text(text)

    def _do_speak():
        backend = get_tts_backend()
        if backend == "silero":
            if not _speak_silero(text):
                _speak_pyttsx3(text)
        elif backend == "pyttsx3":
            _speak_pyttsx3(text)
        else:
            logger.warning("Нет TTS-бэкенда")

    if blocking:
        _do_speak()
        return True
    else:
        t = threading.Thread(target=_do_speak, daemon=True)
        t.start()
        return True


def _preprocess_text(text: str) -> str:
    import re
    text = re.sub(r"[*_~`#]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"https?://\S+", "ссылка", text)
    text = re.sub(r"\[.*?\]", "", text)  # убираем [Подсказка из памяти: ...]
    if len(text) > 600:
        text = text[:600] + "..."
    return text


def preload():
    """Предзагрузить TTS в фоне."""
    backend = get_tts_backend()
    logger.info(f"TTS бэкенд: {backend}")
    if backend == "silero":
        threading.Thread(target=_load_silero_model, daemon=True).start()
