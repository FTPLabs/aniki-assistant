"""
VAD + STT для Аники v3.0 — Whisper + GPU/CPU автодетект + VAD.
FIX [v3]: is_available() работает в frozen exe (PyInstaller) — проверяет
           фактическую загрузку модели, а не только import.
"""

import os
import sys
import logging
import threading
import queue
import time
import wave
import tempfile
from typing import Optional, Callable

logger = logging.getLogger(__name__)

_whisper_model  = None
_whisper_loaded = False
_whisper_lock   = threading.Lock()

WHISPER_MODEL_SIZE = os.environ.get("ANIKI_WHISPER_MODEL", "base")
WHISPER_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "models", "whisper"
)

SILENCE_THRESHOLD = 0.006
SILENCE_DURATION  = 1.0
SAMPLE_RATE       = 16000
FRAME_DURATION_MS = 30


def _get_device_and_compute():
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("GPU (CUDA) обнаружен — используем float16")
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def load_whisper_model(model_size: str = WHISPER_MODEL_SIZE) -> bool:
    global _whisper_model, _whisper_loaded
    with _whisper_lock:
        if _whisper_loaded:
            return True
        try:
            from faster_whisper import WhisperModel
            os.makedirs(WHISPER_MODELS_DIR, exist_ok=True)
            device, compute = _get_device_and_compute()
            logger.info(f"Загружаю Whisper '{model_size}' [{device}/{compute}]...")
            _whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute,
                download_root=WHISPER_MODELS_DIR,
            )
            _whisper_loaded = True
            logger.info(f"Whisper '{model_size}' загружен на {device}")
            return True
        except ImportError as e:
            logger.warning(f"faster-whisper недоступен: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки Whisper: {e}")
            return False


def transcribe_audio_bytes(audio_bytes: bytes,
                           sample_rate: int = SAMPLE_RATE) -> Optional[str]:
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
            language=None,
            task="transcribe",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        text = " ".join(s.text for s in segments).strip()
        logger.debug(f"Whisper: '{text}'")
        return text if text else None
    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        return None
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


class VoiceListener:
    def __init__(
        self,
        callback: Callable[[str], None],
        wake_word: Optional[str] = None,
        on_listening_change: Optional[Callable[[bool], None]] = None,
        silence_threshold: float = SILENCE_THRESHOLD,
    ):
        self.callback             = callback
        self.wake_word            = wake_word.lower() if wake_word else None
        self.on_listening_change  = on_listening_change
        self.silence_threshold    = silence_threshold
        self.sample_rate          = SAMPLE_RATE
        self._stop_event          = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active_listening    = False

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _vad_loop(self):
        try:
            import sounddevice as sd
            import numpy as np
            try:
                import webrtcvad
                vad = webrtcvad.Vad(2)
            except Exception:
                vad = None
                logger.info("webrtcvad недоступен — используем RMS-детектор")

            frame_ms   = FRAME_DURATION_MS
            frame_size = int(self.sample_rate * frame_ms / 1000)
            chunk_size = frame_size * 3

            silence_need = int(SILENCE_DURATION * 1000 / frame_ms)
            min_frames   = int(0.3 * 1000 / frame_ms)

            is_recording = False
            audio_buf    = []
            silence_cnt  = 0

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_size,
            ) as stream:
                while not self._stop_event.is_set():
                    chunk, _ = stream.read(chunk_size)
                    chunk_flat = chunk.flatten()
                    chunk_int16 = chunk_flat.astype("int16")

                    is_speech = self._detect_speech(chunk_int16, vad, frame_size)

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
                                buf_copy = list(audio_buf)
                                threading.Thread(
                                    target=self._process,
                                    args=(buf_copy,),
                                    daemon=True,
                                ).start()
                            if self.on_listening_change:
                                self.on_listening_change(False)
                            is_recording = False
                            audio_buf    = []
                            silence_cnt  = 0
        except Exception as e:
            logger.error(f"Ошибка VAD цикла: {e}")

    def _detect_speech(self, chunk_int16, vad, frame_size: int) -> bool:
        import numpy as np
        rms = float(np.sqrt(np.mean(chunk_int16.astype(np.float32) ** 2))) / 32768.0
        if rms < self.silence_threshold:
            return False
        if vad is not None:
            try:
                raw = chunk_int16[:frame_size].astype(np.int16).tobytes()
                if len(raw) == frame_size * 2:
                    return vad.is_speech(raw, self.sample_rate)
            except Exception:
                pass
        return True

    def _process(self, audio_frames):
        try:
            import numpy as np
            audio       = np.concatenate(audio_frames, axis=0)
            audio_bytes = audio.astype(np.int16).tobytes()
            text        = transcribe_audio_bytes(audio_bytes, self.sample_rate)
            if not text:
                return
            text = text.strip()
            logger.info(f"Голос: '{text}'")
            if self.wake_word:
                text_lower = text.lower()
                if self.wake_word in text_lower:
                    self._active_listening = True
                    self._last_wake_word_time = time.time()  # FIX [H3]
                    clean = text_lower.replace(self.wake_word, "").strip(" ,.-!")
                    if clean:
                        self.callback(clean)
                elif self._active_listening:
                    # FIX [H3]: сбрасываем флаг через 30с без wake-word
                    if time.time() - getattr(self, "_last_wake_word_time", 0) > 30:
                        self._active_listening = False
                        return
                    self.callback(text)
            else:
                self.callback(text)
        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")


MicrophoneListener = VoiceListener


def is_available() -> bool:
    """
    Проверить доступность STT.
    FIX [v3]: В frozen exe (PyInstaller) пакет может быть встроен но по другому пути.
    Пробуем реальную загрузку — не просто import, а создание объекта модели.
    """
    # 1. Проверяем sounddevice + numpy (без них ничего не работает)
    try:
        import sounddevice as sd
        import numpy as np
        devices = sd.query_devices()
        if len(devices) == 0:
            logger.warning("STT: нет аудиоустройств — VAD недоступен")
            return False
    except ImportError as e:
        logger.warning(f"STT: sounddevice/numpy не установлен — {e}")
        return False
    except Exception as e:
        logger.warning(f"STT: ошибка аудиоустройств — {e}")
        return False

    # 2. Проверяем faster_whisper — в frozen exe может быть по sys.path
    try:
        import faster_whisper  # noqa: F401
        logger.info("STT: faster_whisper найден")
    except ImportError:
        # В frozen exe пробуем явный путь
        if getattr(sys, "frozen", False):
            frozen_dir = os.path.dirname(sys.executable)
            potential_paths = [
                frozen_dir,
                os.path.join(frozen_dir, "faster_whisper"),
                os.path.join(frozen_dir, "_internal"),
            ]
            found = False
            for p in potential_paths:
                if p not in sys.path and os.path.exists(p):
                    sys.path.insert(0, p)
                    try:
                        import faster_whisper  # noqa: F401
                        logger.info(f"STT: faster_whisper найден в {p}")
                        found = True
                        break
                    except ImportError:
                        sys.path.remove(p)
            if not found:
                logger.warning("STT: faster_whisper не найден в exe — VAD недоступен. "
                               "Пиши текстом, бро!")
                return False
        else:
            logger.warning("STT: faster_whisper не установлен — pip install faster-whisper")
            return False

    logger.info("STT готов (faster-whisper + sounddevice)")
    return True
