"""
  VAD + STT для Аники v3.2 — Whisper + silero-vad (мгновенный старт, ML-точность).
  silero-vad: чистый PyTorch, нет C++ зависимостей, работает из коробки.
  Fallback: webrtcvad → RMS-детектор.
  """

  import os, sys, logging, threading, queue, time, wave, tempfile
  from typing import Optional, Callable

  logger = logging.getLogger(__name__)

  _whisper_model  = None
  _whisper_loaded = False
  _whisper_lock   = threading.Lock()

  _silero_vad_model = None
  _silero_vad_utils = None
  _silero_vad_lock  = threading.Lock()

  WHISPER_MODEL_SIZE = os.environ.get("ANIKI_WHISPER_MODEL", "base")
  WHISPER_MODELS_DIR = os.path.join(
      os.path.dirname(os.path.dirname(__file__)), "data", "models", "whisper"
  )

  SILENCE_THRESHOLD = 0.005
  SILENCE_DURATION  = 0.8   # секунды тишины до конца фразы
  SAMPLE_RATE       = 16000
  FRAME_MS          = 32    # silero-vad требует 32ms @ 16kHz


  def _get_device_and_compute():
      try:
          import torch
          if torch.cuda.is_available():
              return "cuda", "float16"
      except Exception:
          pass
      return "cpu", "int8"


  def _load_silero_vad():
      """Загружает silero-vad из torch.hub (кэшируется автоматически)."""
      global _silero_vad_model, _silero_vad_utils
      with _silero_vad_lock:
          if _silero_vad_model is not None:
              return _silero_vad_model, _silero_vad_utils
          try:
              import torch
              torch.hub.set_dir(os.path.join(
                  os.path.dirname(os.path.dirname(__file__)), "data", "models", "silero_vad"
              ))
              model, utils = torch.hub.load(
                  repo_or_dir="snakers4/silero-vad",
                  model="silero_vad",
                  force_reload=False,
                  trust_repo=True,
                  verbose=False,
              )
              _silero_vad_model = model
              _silero_vad_utils = utils
              logger.info("silero-vad загружен ✓")
              return model, utils
          except Exception as e:
              logger.info(f"silero-vad недоступен ({e}), используем fallback")
              return None, None


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
                  model_size, device=device, compute_type=compute,
                  download_root=WHISPER_MODELS_DIR,
              )
              _whisper_loaded = True
              logger.info(f"Whisper '{model_size}' загружен на {device}")
              return True
          except Exception as e:
              logger.error(f"Ошибка загрузки Whisper: {e}")
              return False


  def transcribe_audio_bytes(audio_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> Optional[str]:
      if not _whisper_loaded:
          if not load_whisper_model():
              return None
      with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
          tmp = f.name
      try:
          with wave.open(tmp, "wb") as wf:
              wf.setnchannels(1); wf.setsampwidth(2)
              wf.setframerate(sample_rate); wf.writeframes(audio_bytes)
          segments, _ = _whisper_model.transcribe(
              tmp, language=None, task="transcribe",
              beam_size=5, best_of=5, temperature=0.0,
              vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
          )
          text = " ".join(s.text for s in segments).strip()
          logger.debug(f"Whisper: '{text}'")
          return text if text else None
      except Exception as e:
          logger.error(f"Ошибка транскрипции: {e}")
          return None
      finally:
          try: os.unlink(tmp)
          except: pass


  class VoiceListener:
      def __init__(
          self,
          callback: Callable[[str], None],
          wake_word: Optional[str] = None,
          on_listening_change: Optional[Callable[[bool], None]] = None,
          silence_threshold: float = SILENCE_THRESHOLD,
      ):
          self.callback            = callback
          self.wake_word           = wake_word.lower() if wake_word else None
          self.on_listening_change = on_listening_change
          self.silence_threshold   = silence_threshold
          self.sample_rate         = SAMPLE_RATE
          self._stop_event         = threading.Event()
          self._thread: Optional[threading.Thread] = None
          self._active_listening   = False
          self._last_wake_time     = 0.0

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

              # Пробуем загрузить silero-vad
              silero_model, _ = _load_silero_vad()

              # Fallback: webrtcvad
              vad_webrtc = None
              if silero_model is None:
                  try:
                      import webrtcvad
                      vad_webrtc = webrtcvad.Vad(2)
                      logger.info("Используем webrtcvad")
                  except Exception:
                      logger.info("VAD: только RMS-детектор")

              frame_size = int(self.sample_rate * FRAME_MS / 1000)  # 512 сэмплов
              chunk_size = frame_size * 4

              silence_need = int(SILENCE_DURATION * 1000 / FRAME_MS)
              min_frames   = max(3, int(0.25 * 1000 / FRAME_MS))

              is_recording = False
              audio_buf    = []
              silence_cnt  = 0

              with sd.InputStream(
                  samplerate=self.sample_rate,
                  channels=1, dtype="int16",
                  blocksize=chunk_size,
              ) as stream:
                  while not self._stop_event.is_set():
                      chunk, _ = stream.read(chunk_size)
                      chunk_flat   = chunk.flatten()
                      chunk_int16  = chunk_flat.astype("int16")

                      is_speech = self._detect_speech(
                          chunk_int16, chunk_flat, silero_model, vad_webrtc, frame_size
                      )

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
                                      target=self._process, args=(buf_copy,), daemon=True
                                  ).start()
                              if self.on_listening_change:
                                  self.on_listening_change(False)
                              is_recording = False
                              audio_buf    = []
                              silence_cnt  = 0
          except Exception as e:
              logger.error(f"Ошибка VAD цикла: {e}")

      def _detect_speech(self, chunk_int16, chunk_float, silero_model, vad_webrtc, frame_size: int) -> bool:
          import numpy as np
          rms = float(np.sqrt(np.mean(chunk_int16.astype(np.float32) ** 2))) / 32768.0
          if rms < self.silence_threshold:
              return False

          # 1. silero-vad (лучший)
          if silero_model is not None:
              try:
                  import torch
                  audio_tensor = torch.from_numpy(
                      chunk_float.astype(np.float32) / 32768.0
                  ).unsqueeze(0)
                  prob = silero_model(audio_tensor, self.sample_rate).item()
                  return prob > 0.4
              except Exception:
                  pass

          # 2. webrtcvad (fallback)
          if vad_webrtc is not None:
              try:
                  raw = chunk_int16[:frame_size].astype(np.int16).tobytes()
                  if len(raw) == frame_size * 2:
                      return vad_webrtc.is_speech(raw, self.sample_rate)
              except Exception:
                  pass

          # 3. RMS-детектор (последний рубеж)
          return rms > self.silence_threshold * 2

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
                      self._last_wake_time   = time.time()
                      clean = text_lower.replace(self.wake_word, "").strip(" ,.-!")
                      if clean:
                          self.callback(clean)
                  elif self._active_listening:
                      if time.time() - self._last_wake_time > 30:
                          self._active_listening = False
                          return
                      self.callback(text)
              else:
                  self.callback(text)
          except Exception as e:
              logger.error(f"Ошибка обработки аудио: {e}")


  MicrophoneListener = VoiceListener


  def is_available() -> bool:
      try:
          import sounddevice as sd
          import numpy as np
          if len(sd.query_devices()) == 0:
              return False
      except Exception:
          return False
      try:
          import torch
          return True  # silero-vad будет работать
      except Exception:
          pass
      try:
          import webrtcvad
          return True
      except Exception:
          pass
      return True  # RMS fallback всегда работает
  