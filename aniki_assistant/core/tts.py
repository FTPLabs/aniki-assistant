"""
TTS Аники v2.3 — голос Билли Херрингтона.
FIX [C3]: _ensure_billy_reference() скачивает реф-аудио с рабочего URL.
FIX [M1]: get_tts_backend() проверяет реальную загрузку модели XTTS.
FIX [M5]: StreamTTS.__del__ вызывает stop() при уничтожении объекта.
"""

import os
import logging
import threading
import queue
import re
from typing import Optional, Callable

logger = logging.getLogger(__name__)

_tts_lock      = threading.Lock()
_silero_model  = None
_silero_loaded = False
_xtts_model    = None
_xtts_loaded   = False
_sample_rate   = 24000

SILERO_SPEAKER  = "aidar"
SILERO_LANG     = "ru"
SILERO_MODEL_ID = "v4_ru"

# ── Голосовые клипы Билли ─────────────────────────────────────────────────────
BILLY_CLIPS = {
    "are you ready":           "are_you_ready.mp3",
    "let's go":                "lets_go.mp3",
    "let me go":               "lets_go.mp3",
    "no pain no gain":         "no_pain_no_gain.mp3",
    "no pain, no gain":        "no_pain_no_gain.mp3",
    "i'm your man":            "im_your_man.mp3",
    "right here right now":    "right_here.mp3",
    "yeah buddy":              "yeah_buddy.mp3",
    "come on":                 "come_on.mp3",
    "wrestle with the best":   "wrestle.mp3",
    "it's a man's world":      "mans_world.mp3",
    "исполняю":                "lets_go.mp3",
    "сделано":                 "yeah_buddy.mp3",
    "готово бро":              "yeah_buddy.mp3",
    "понял бро":               "come_on.mp3",
}

_CLIPS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "voice"
)

# FIX [C3]: рабочий URL для референсного аудио Билли (публичный Archive.org)
_BILLY_REF_URLS = [
    "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds/lets_go.mp3",
    "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds/are_you_ready.mp3",
]
_BILLY_REF_PATH = os.path.join(_CLIPS_DIR, "reference", "billy_ref.wav")


def _play_clip(filename: str) -> bool:
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
    text_lower = text.lower()
    for phrase, filename in BILLY_CLIPS.items():
        if phrase in text_lower:
            if _play_clip(filename):
                return True
    return False


# ── XTTS-v2 — клонирование голоса Билли ──────────────────────────────────────

def _ensure_billy_reference() -> Optional[str]:
    """
    FIX [C3]: реальная логика получения референс-аудио.
    Приоритет: кэш WAV → любой mp3 клип → скачать с archive.org → None.
    """
    os.makedirs(os.path.dirname(_BILLY_REF_PATH), exist_ok=True)

    # 1. Уже есть готовый WAV-референс
    if os.path.exists(_BILLY_REF_PATH):
        return _BILLY_REF_PATH

    # 2. Конвертируем существующий mp3 клип в wav через ffmpeg
    for clip in BILLY_CLIPS.values():
        p = os.path.join(_CLIPS_DIR, clip)
        if os.path.exists(p) and p.endswith(".mp3"):
            try:
                import subprocess
                r = subprocess.run(
                    ["ffmpeg", "-y", "-i", p, "-ar", "22050", "-ac", "1", _BILLY_REF_PATH],
                    capture_output=True, timeout=10
                )
                if r.returncode == 0 and os.path.exists(_BILLY_REF_PATH):
                    logger.info("Billy reference: сконвертирован из mp3")
                    return _BILLY_REF_PATH
            except Exception:
                pass

    # 3. Скачиваем mp3 с archive.org и конвертируем
    import urllib.request
    tmp_mp3 = _BILLY_REF_PATH + ".tmp.mp3"
    for url in _BILLY_REF_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AnikiBuddy/2.3"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                with open(tmp_mp3, "wb") as f:
                    f.write(resp.read())
            import subprocess
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "22050", "-ac", "1", _BILLY_REF_PATH],
                capture_output=True, timeout=15
            )
            if r.returncode == 0 and os.path.exists(_BILLY_REF_PATH):
                logger.info(f"Billy reference: скачан и сконвертирован из {url}")
                try:
                    os.unlink(tmp_mp3)
                except Exception:
                    pass
                return _BILLY_REF_PATH
        except Exception as e:
            logger.debug(f"Не удалось скачать billy ref из {url}: {e}")

    try:
        if os.path.exists(tmp_mp3):
            os.unlink(tmp_mp3)
    except Exception:
        pass

    logger.warning("Billy reference audio не найден — XTTS использует Silero")
    return None


def _load_xtts() -> bool:
    global _xtts_model, _xtts_loaded
    if _xtts_loaded:
        return True
    try:
        from TTS.api import TTS
        ref = _ensure_billy_reference()
        if not ref:
            logger.info("XTTS: нет референсного аудио Билли — используем Silero")
            return False
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Загружаю XTTS-v2 [{device}]...")
        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        model.to(device)
        _xtts_model = (model, ref, device)
        _xtts_loaded = True
        logger.info("XTTS-v2 загружен — голос Билли активен!")
        return True
    except ImportError:
        logger.info("TTS-пакет не установлен — используем Silero (pip install TTS для голоса Билли)")
        return False
    except Exception as e:
        logger.warning(f"XTTS недоступен: {e}")
        return False


def _speak_xtts(text: str) -> bool:
    if not _xtts_loaded:
        return False
    try:
        model, ref_audio, device = _xtts_model
        import tempfile, sounddevice as sd, soundfile as sf
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        model.tts_to_file(
            text=text,
            speaker_wav=ref_audio,
            language="ru",
            file_path=tmp,
        )
        data, sr = sf.read(tmp, dtype="float32")
        sd.play(data, sr)
        sd.wait()
        os.unlink(tmp)
        return True
    except Exception as e:
        logger.error(f"XTTS ошибка: {e}")
        return False


# ── Silero TTS ────────────────────────────────────────────────────────────────

def _load_silero_model(retry: int = 0) -> bool:
    global _silero_model, _silero_loaded, _sample_rate
    if retry > 1:
        logger.error("Silero TTS: не удалось загрузить")
        return False
    try:
        import torch
        models_dir  = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "models"
        )
        os.makedirs(models_dir, exist_ok=True)
        model_path  = os.path.join(models_dir, f"silero_tts_{SILERO_MODEL_ID}.pt")

        if os.path.exists(model_path):
            try:
                model = torch.package.PackageImporter(model_path).load_pickle(
                    "tts_models", "model"
                )
                logger.info("Silero TTS загружен из кэша")
            except Exception:
                logger.warning("Кэш Silero повреждён — перекачиваю...")
                os.remove(model_path)
                return _load_silero_model(retry=retry + 1)
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
        _silero_model  = model
        _silero_loaded = True
        _sample_rate   = 24000
        logger.info(f"Silero TTS готов (голос: {SILERO_SPEAKER})")
        return True
    except Exception as e:
        logger.warning(f"Silero TTS недоступен: {e}")
        return False


def _speak_silero(text: str) -> bool:
    global _silero_model, _sample_rate
    try:
        import torch
        import sounddevice as sd
        with _tts_lock:
            if not _silero_loaded:
                if not _load_silero_model():
                    return False
            audio = _silero_model.apply_tts(
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
            if ("russian" in nl or "ru" in il or "pavel" in nl):
                chosen = v.id
                break
        if chosen:
            engine.setProperty("voice", chosen)
        engine.setProperty("rate", 155)
        engine.setProperty("volume", 0.95)
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        logger.error(f"Ошибка pyttsx3: {e}")
        return False


_tts_backend: Optional[str] = None


def get_tts_backend() -> str:
    """
    FIX [M1]: возвращаем 'xtts' ТОЛЬКО если модель уже загружена.
    При первом вызове — выбираем по наличию пакетов, но не дублируем Silero-fallback.
    """
    global _tts_backend
    if _tts_backend:
        return _tts_backend
    # Если XTTS уже загружен — используем
    if _xtts_loaded:
        _tts_backend = "xtts"
        return _tts_backend
    # Определяем доступный бэкенд по установленным пакетам
    try:
        import torch, sounddevice  # noqa
        _tts_backend = "silero"
        return _tts_backend
    except ImportError:
        pass
    try:
        import pyttsx3  # noqa
        _tts_backend = "pyttsx3"
        return _tts_backend
    except ImportError:
        pass
    _tts_backend = "none"
    return _tts_backend


def _do_speak(text: str):
    if _try_billy_clip(text):
        return
    backend = get_tts_backend()
    if backend == "xtts":
        if _speak_xtts(text):
            return
        if not _speak_silero(text):
            _speak_pyttsx3(text)
    elif backend == "silero":
        if not _speak_silero(text):
            _speak_pyttsx3(text)
    elif backend == "pyttsx3":
        _speak_pyttsx3(text)


def speak(text: str, blocking: bool = True) -> bool:
    if not text or not text.strip():
        return False
    text = _preprocess_text(text)
    if blocking:
        _do_speak(text)
        return True
    threading.Thread(target=_do_speak, args=(text,), daemon=True).start()
    return True


# ── СТРИМИНГ TTS ──────────────────────────────────────────────────────────────

class StreamTTS:
    SENTENCE_ENDS = re.compile(r'([.!?…]+[\s\n]|[.!?…]+$)')

    def __init__(self, on_start: Optional[Callable] = None,
                 on_done: Optional[Callable] = None):
        self._buf    = ""
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.on_start = on_start
        self.on_done  = on_done
        self._spoken  = 0
        self._stopped = False

    def feed(self, token: str):
        self._buf += token
        while True:
            m = self.SENTENCE_ENDS.search(self._buf)
            if not m:
                break
            end      = m.end()
            sentence = self._buf[:end].strip()
            self._buf = self._buf[end:]
            if sentence and len(sentence) > 5:
                self._enqueue(sentence)

    def flush(self):
        tail = self._buf.strip()
        if tail and len(tail) > 3:
            self._enqueue(tail)
        self._buf = ""
        self._q.join()

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
        """FIX [M5]: корректная остановка — отправляем sentinel и ждём."""
        if self._stopped:
            return
        self._stopped = True
        if self.on_done:
            self.on_done()
        self._q.put(None)

    def __del__(self):
        """FIX [M5]: гарантируем остановку при уничтожении объекта."""
        self.stop()


def _preprocess_text(text: str) -> str:
    text = re.sub(r"[*_~`#]", "", text)
    text = re.sub(r"\s+",     " ", text).strip()
    text = re.sub(r"https?://\S+", "ссылка", text)
    text = re.sub(r"\[.*?\]", "", text)
    if len(text) > 600:
        text = text[:600] + "..."
    return text


def preload():
    backend = get_tts_backend()
    logger.info(f"TTS бэкенд: {backend}")
    if backend == "xtts":
        threading.Thread(target=_load_xtts, daemon=True).start()
    elif backend == "silero":
        threading.Thread(target=_load_silero_model, daemon=True).start()
