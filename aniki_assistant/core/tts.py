"""
Синтез речи (TTS) для Аники v2.2.
Silero TTS v4 (офлайн) + стриминг по предложениям + голосовые клипы Билли.
FIX: нет бесконечной рекурсии при повреждённом кэше.
"""

import os
import logging
import threading
import queue
import re
from typing import Optional, Callable

logger = logging.getLogger(__name__)

_tts_lock    = threading.Lock()
_model       = None
_model_loaded = False
_sample_rate = 24000

SILERO_SPEAKER  = "aidar"
SILERO_LANG     = "ru"
SILERO_MODEL_ID = "v4_ru"

# ── Голосовые клипы Билли Херрингтона ─────────────────────────────────────────
# Ключ — фраза для поиска совпадения, значение — имя .mp3 файла в data/voice/
BILLY_CLIPS = {
    "are you ready":       "are_you_ready.mp3",
    "let's go":            "lets_go.mp3",
    "no pain no gain":     "no_pain_no_gain.mp3",
    "i'm your man":        "im_your_man.mp3",
    "right here right now":"right_here.mp3",
    "yeah buddy":          "yeah_buddy.mp3",
    "come on":             "come_on.mp3",
    "wrestle with the best":"wrestle.mp3",
}

_CLIPS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "voice"
)


def _play_clip(filename: str) -> bool:
    """Воспроизвести заготовленный аудиоклип Билли."""
    path = os.path.join(_CLIPS_DIR, filename)
    if not os.path.exists(path):
        return False
    try:
        import sounddevice as sd
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32")
        sd.play(data, sr)
        sd.wait()
        return True
    except Exception:
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            return True
        except Exception as e:
            logger.debug(f"Клип недоступен: {e}")
            return False


def _try_billy_clip(text: str) -> bool:
    """Попытаться воспроизвести клип Билли если текст содержит его фразу."""
    text_lower = text.lower()
    for phrase, filename in BILLY_CLIPS.items():
        if phrase in text_lower:
            if _play_clip(filename):
                return True
    return False


# ── Silero TTS ────────────────────────────────────────────────────────────────

def _load_silero_model(retry: int = 0) -> bool:
    """
    FIX: max_retry=1 — нет бесконечной рекурсии при повреждённом кэше.
    """
    global _model, _model_loaded, _sample_rate
    if retry > 1:
        logger.error("Silero TTS: не удалось загрузить после 2 попыток")
        return False
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
                logger.warning("Кэш Silero повреждён — перекачиваю...")
                os.remove(model_path)
                return _load_silero_model(retry=retry + 1)   # FIX: передаём retry
        else:
            logger.info("Загружаю Silero TTS v4 ru...")
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-models",
                model="silero_tts",
                language=SILERO_LANG,
                speaker=SILERO_MODEL_ID,
                verbose=False,
            )
            torch.save(model, model_path)

        model.to(torch.device("cpu"))
        _model = model
        _model_loaded = True
        _sample_rate = 24000
        logger.info(f"Silero TTS готов (голос: {SILERO_SPEAKER})")
        return True
    except Exception as e:
        logger.warning(f"Silero TTS недоступен: {e}")
        return False


def _speak_silero(text: str) -> bool:
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
            sd.play(audio.numpy(), samplerate=_sample_rate)
            sd.wait()
            return True
    except Exception as e:
        logger.error(f"Ошибка Silero TTS: {e}")
        return False


def _speak_pyttsx3(text: str) -> bool:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        chosen = None
        for v in voices:
            nl, il = v.name.lower(), v.id.lower()
            if ("russian" in nl or "ru" in il or "pavel" in nl) and \
               ("pavel" in nl or "male" in nl or "man" in nl):
                chosen = v.id
                break
        if not chosen:
            for v in voices:
                if "russian" in v.name.lower() or "ru" in v.id.lower():
                    chosen = v.id
                    break
        if chosen:
            engine.setProperty("voice", chosen)
        engine.setProperty("rate", 165)
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
        import torch, sounddevice
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


def _do_speak(text: str):
    # Попытка воспроизвести клип Билли (только для его фирменных фраз)
    if _try_billy_clip(text):
        return
    backend = get_tts_backend()
    if backend == "silero":
        if not _speak_silero(text):
            _speak_pyttsx3(text)
    elif backend == "pyttsx3":
        _speak_pyttsx3(text)


def speak(text: str, blocking: bool = True) -> bool:
    """Воспроизвести текст голосом. blocking=False — в фоне."""
    if not text or not text.strip():
        return False
    text = _preprocess_text(text)
    if blocking:
        _do_speak(text)
        return True
    threading.Thread(target=_do_speak, args=(text,), daemon=True).start()
    return True


# ── СТРИМИНГ TTS — говорит сразу, не ждёт конца ответа ──────────────────────

class StreamTTS:
    """
    Принимает токены по одному, собирает предложения,
    воспроизводит каждое как только оно завершено.
    Используется для того чтобы Аники начинал говорить
    сразу с первого предложения, не дожидаясь конца ответа.
    """
    SENTENCE_ENDS = re.compile(r'([.!?…]+[\s\n]|[.!?…]+$)')

    def __init__(self, on_start: Optional[Callable] = None,
                 on_done: Optional[Callable] = None):
        self._buf   = ""
        self._q     = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.on_start = on_start
        self.on_done  = on_done
        self._spoken  = 0

    def feed(self, token: str):
        """Добавить токен. Говорит сразу как накопится предложение."""
        self._buf += token
        # Ищем границы предложений
        while True:
            m = self.SENTENCE_ENDS.search(self._buf)
            if not m:
                break
            end = m.end()
            sentence = self._buf[:end].strip()
            self._buf = self._buf[end:]
            if sentence and len(sentence) > 5:
                self._enqueue(sentence)

    def flush(self):
        """Договорить остаток буфера."""
        tail = self._buf.strip()
        if tail and len(tail) > 3:
            self._enqueue(tail)
        self._buf = ""
        self._q.join()   # ждём пока очередь опустеет

    def _enqueue(self, sentence: str):
        if self._spoken == 0 and self.on_start:
            self.on_start()
        self._spoken += 1
        self._q.put(sentence)

    def _worker(self):
        while True:
            sentence = self._q.get()
            if sentence is None:
                break
            try:
                _do_speak(_preprocess_text(sentence))
            except Exception as e:
                logger.error(f"StreamTTS error: {e}")
            finally:
                self._q.task_done()

    def stop(self):
        if self.on_done:
            self.on_done()
        self._q.put(None)


def _preprocess_text(text: str) -> str:
    text = re.sub(r"[*_~`#]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"https?://\S+", "ссылка", text)
    text = re.sub(r"\[.*?\]", "", text)
    if len(text) > 600:
        text = text[:600] + "..."
    return text


def preload():
    backend = get_tts_backend()
    logger.info(f"TTS бэкенд: {backend}")
    if backend == "silero":
        threading.Thread(target=_load_silero_model, daemon=True).start()
