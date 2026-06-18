"""
VAD + STT для Аники.
Постоянно слушает микрофон, обнаруживает голос, отправляет в Whisper.
Поддерживает webrtcvad (точный) или amplitude (запасной).
"""

import os
import logging
import threading
import queue
import time
import wave
import tempfile
from typing import Optional, Callable

logger = logging.getLogger(__name__)

_whisper_model = None
_whisper_loaded = False
_whisper_lock   = threading.Lock()

WHISPER_MODEL_SIZE = "small"
WHISPER_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "models", "whisper"
)

# Порог тишины (RMS) — подстрой под своё железо
SILENCE_THRESHOLD = 0.008
SILENCE_DURATION  = 1.2    # секунд тишины = конец фразы
SAMPLE_RATE       = 16000
FRAME_DURATION_MS = 30     # для webrtcvad: 10, 20 или 30


def load_whisper_model(model_size: str = WHISPER_MODEL_SIZE) -> bool:
    global _whisper_model, _whisper_loaded
    with _whisper_lock:
        if _whisper_loaded:
            return True
        try:
            from faster_whisper import WhisperModel
            os.makedirs(WHISPER_MODELS_DIR, exist_ok=True)
            logger.info(f"Загружаю Whisper '{model_size}'...")
            _whisper_model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=WHISPER_MODELS_DIR,
            )
            _whisper_loaded = True
            logger.info("Whisper загружен")
            return True
        except ImportError:
            logger.error("faster-whisper не установлен")
            return False
        except Exception as e:
            logger.error(f"Ошибка Whisper: {e}")
            return False


def transcribe_audio_bytes(audio_bytes: bytes,
                           sample_rate: int = SAMPLE_RATE) -> Optional[str]:
    """Транскрибировать аудио в текст."""
    if not _whisper_loaded:
        if not load_whisper_model():
            return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)
        segments, info = _whisper_model.transcribe(
            tmp,
            language=None,       # автоопределение ru/en
            task="transcribe",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        text = " ".join(s.text for s in segments).strip()
        logger.debug(f"Распознано: '{text}' [{info.language}]")
        return text or None
    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        return None
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def transcribe_audio_file(path: str) -> Optional[str]:
    if not _whisper_loaded:
        load_whisper_model()
    try:
        segments, info = _whisper_model.transcribe(
            path, language=None, task="transcribe",
            beam_size=5, temperature=0.0,
            vad_filter=True,
        )
        return " ".join(s.text for s in segments).strip() or None
    except Exception as e:
        logger.error(f"Ошибка транскрипции файла: {e}")
        return None


# ── VAD — определение речи ────────────────────────────────────────────────────

def _try_webrtcvad():
    """Попытаться импортировать webrtcvad."""
    try:
        import webrtcvad
        return webrtcvad
    except ImportError:
        return None


class VoiceListener:
    """
    Постоянно слушает микрофон.
    При обнаружении речи записывает, транскрибирует, вызывает callback(text).

    Поддерживает будильник-слово: если задан wake_word, реагирует только
    когда пользователь сказал его (например, "аники").
    Без wake_word — реагирует на всё.
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        wake_word: Optional[str] = None,
        silence_threshold: float = SILENCE_THRESHOLD,
        silence_duration:  float = SILENCE_DURATION,
        sample_rate:       int   = SAMPLE_RATE,
        on_listening_change: Optional[Callable[[bool], None]] = None,
    ):
        self.callback           = callback
        self.wake_word          = wake_word.lower() if wake_word else None
        self.silence_threshold  = silence_threshold
        self.silence_duration   = silence_duration
        self.sample_rate        = sample_rate
        self.on_listening_change = on_listening_change

        self._running         = False
        self._thread: Optional[threading.Thread] = None
        self._audio_q: queue.Queue = queue.Queue()
        self._webrtcvad       = _try_webrtcvad()

        # Режим активного слушания (если wake_word задан и произнесён)
        self._active_listening = (wake_word is None)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        if not _whisper_loaded:
            load_whisper_model()
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("VAD запущен — слушаю микрофон")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("VAD остановлен")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Внутренний цикл ────────────────────────────────────────────────────────

    def _listen_loop(self):
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.error("sounddevice / numpy не установлены")
            return

        frame_size   = int(self.sample_rate * FRAME_DURATION_MS / 1000)
        silence_need = int(self.silence_duration / (FRAME_DURATION_MS / 1000))
        min_frames   = 8    # минимум фреймов для обработки (~240 мс)

        # Инициализация webrtcvad если доступен
        vad = None
        if self._webrtcvad:
            try:
                vad = self._webrtcvad.Vad(2)   # агрессивность 0-3
                logger.info("WebRTC VAD активен")
            except Exception:
                vad = None

        audio_buf    = []
        silence_cnt  = 0
        is_recording = False

        def audio_cb(indata, frames, time_info, status):
            self._audio_q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_size,
                callback=audio_cb,
            ):
                logger.info("Микрофон открыт, жду речь...")
                while self._running:
                    try:
                        chunk = self._audio_q.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    chunk_flat = chunk.flatten()

                    # Определяем наличие речи
                    is_speech = self._detect_speech(chunk_flat, vad, frame_size)

                    if is_speech:
                        if not is_recording:
                            is_recording = True
                            audio_buf    = []
                            silence_cnt  = 0
                            if self.on_listening_change:
                                self.on_listening_change(True)
                        audio_buf.append(chunk_flat)
                        silence_cnt = 0
                    elif is_recording:
                        audio_buf.append(chunk_flat)
                        silence_cnt += 1
                        if silence_cnt >= silence_need:
                            if len(audio_buf) >= min_frames:
                                # Обрабатываем в фоне, не блокируя VAD
                                buf_copy = list(audio_buf)
                                t = threading.Thread(
                                    target=self._process,
                                    args=(buf_copy,),
                                    daemon=True,
                                )
                                t.start()
                            if self.on_listening_change:
                                self.on_listening_change(False)
                            is_recording = False
                            audio_buf    = []
                            silence_cnt  = 0
        except Exception as e:
            logger.error(f"Ошибка VAD цикла: {e}")

    def _detect_speech(self, chunk_int16, vad, frame_size: int) -> bool:
        """Определить есть ли речь в чанке."""
        import numpy as np

        # Амплитудный тест (быстрый)
        rms = float(np.sqrt(np.mean(chunk_int16.astype(np.float32) ** 2))) / 32768.0
        if rms < self.silence_threshold:
            return False

        # WebRTC VAD (точный, если доступен)
        if vad is not None:
            try:
                raw = chunk_int16[:frame_size].astype(np.int16).tobytes()
                if len(raw) == frame_size * 2:
                    return vad.is_speech(raw, self.sample_rate)
            except Exception:
                pass

        return True   # амплитуда прошла, webrtcvad недоступен

    def _process(self, audio_frames):
        """Транскрибировать и вызвать callback."""
        try:
            import numpy as np
            audio = np.concatenate(audio_frames, axis=0)
            audio_bytes = audio.astype(np.int16).tobytes()
            text = transcribe_audio_bytes(audio_bytes, self.sample_rate)
            if not text:
                return

            text = text.strip()
            logger.info(f"Голос: '{text}'")

            if self.wake_word:
                text_lower = text.lower()
                if self.wake_word in text_lower:
                    self._active_listening = True
                    clean = text_lower.replace(self.wake_word, "").strip(" ,.-!")
                    if clean:
                        self.callback(clean)
                    # Если произнесено только имя — просто активируемся (не отправляем пустой запрос)
                elif self._active_listening:
                    self.callback(text)
                    # Остаёмся в активном режиме — Аники помнит контекст
            else:
                self.callback(text)

        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")


# ── Совместимость — старый класс MicrophoneListener ──────────────────────────

MicrophoneListener = VoiceListener


def is_available() -> bool:
    """Проверить доступность STT."""
    try:
        import faster_whisper
        import sounddevice
        import numpy
        return True
    except ImportError:
        return False
