"""
Распознавание речи (STT) для Аники.
Использует faster-whisper — офлайн, поддерживает русский + английский.
"""

import os
import io
import logging
import threading
import queue
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)

_model = None
_model_loaded = False
_model_lock = threading.Lock()

WHISPER_MODEL_SIZE = "small"
WHISPER_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "models", "whisper"
)


def load_whisper_model(model_size: str = WHISPER_MODEL_SIZE) -> bool:
    """Загрузить модель Whisper."""
    global _model, _model_loaded
    with _model_lock:
        if _model_loaded:
            return True
        try:
            from faster_whisper import WhisperModel
            os.makedirs(WHISPER_MODELS_DIR, exist_ok=True)

            logger.info(f"Загружаю Whisper модель '{model_size}'...")
            _model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=WHISPER_MODELS_DIR,
            )
            _model_loaded = True
            logger.info("Whisper модель загружена")
            return True
        except ImportError:
            logger.error("faster-whisper не установлен. Запусти: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки Whisper: {e}")
            return False


def transcribe_audio_file(audio_path: str) -> Optional[str]:
    """Транскрибировать аудиофайл."""
    if not _model_loaded:
        if not load_whisper_model():
            return None
    try:
        segments, info = _model.transcribe(
            audio_path,
            language=None,
            task="transcribe",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text for seg in segments).strip()
        logger.debug(f"Распознано: '{text}' (язык: {info.language}, {info.language_probability:.0%})")
        return text if text else None
    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        return None


def transcribe_audio_bytes(audio_bytes: bytes, sample_rate: int = 16000) -> Optional[str]:
    """Транскрибировать аудио из байтов."""
    import tempfile
    import wave

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

        return transcribe_audio_file(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


class MicrophoneListener:
    """
    Непрерывное прослушивание микрофона с определением речи (VAD).
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        wake_word: Optional[str] = None,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        sample_rate: int = 16000,
    ):
        self.callback = callback
        self.wake_word = wake_word.lower() if wake_word else None
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.sample_rate = sample_rate
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._listening_mode = True if wake_word is None else False

    def start(self):
        """Запустить прослушивание."""
        if not _model_loaded:
            load_whisper_model()
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Прослушивание микрофона запущено")

    def stop(self):
        """Остановить прослушивание."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Прослушивание микрофона остановлено")

    def _listen_loop(self):
        """Основной цикл прослушивания."""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.error("sounddevice или numpy не установлены")
            return

        chunk_duration = 0.1
        chunk_size = int(self.sample_rate * chunk_duration)

        audio_buffer = []
        silence_counter = 0
        is_recording = False
        min_chunks_to_process = 10

        logger.info("Готов к прослушиванию...")

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio status: {status}")
            self._audio_queue.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_size,
                callback=audio_callback,
            ):
                while self._running:
                    try:
                        chunk = self._audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    amplitude = float(np.abs(chunk).mean())
                    is_speech = amplitude > self.silence_threshold

                    if is_speech:
                        if not is_recording:
                            is_recording = True
                            audio_buffer = []
                            silence_counter = 0
                            logger.debug("Начало записи речи...")

                        audio_buffer.append(chunk)
                        silence_counter = 0

                    elif is_recording:
                        audio_buffer.append(chunk)
                        silence_counter += 1
                        silence_chunks_needed = int(self.silence_duration / chunk_duration)

                        if silence_counter >= silence_chunks_needed:
                            if len(audio_buffer) >= min_chunks_to_process:
                                self._process_audio(audio_buffer, np)
                            is_recording = False
                            audio_buffer = []
                            silence_counter = 0

        except Exception as e:
            logger.error(f"Ошибка прослушивания: {e}")

    def _process_audio(self, audio_chunks, np):
        """Обработать записанный аудио-буфер."""
        try:
            audio_data = np.concatenate(audio_chunks, axis=0).flatten()
            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()

            text = transcribe_audio_bytes(audio_bytes, self.sample_rate)

            if not text:
                return

            text = text.strip()
            logger.info(f"Распознан текст: '{text}'")

            if self.wake_word:
                text_lower = text.lower()
                if self.wake_word in text_lower:
                    self._listening_mode = True
                    clean = text_lower.replace(self.wake_word, "").strip()
                    if clean:
                        self.callback(clean)
                    else:
                        self.callback("аники слушает")
                elif self._listening_mode:
                    self.callback(text)
                    self._listening_mode = False
            else:
                self.callback(text)

        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")


def is_available() -> bool:
    """Проверить доступность STT."""
    try:
        import faster_whisper
        import sounddevice
        import numpy
        return True
    except ImportError:
        return False
