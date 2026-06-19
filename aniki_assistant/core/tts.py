"""
  TTS Аники v3.2 — голос Билли Херрингтона + 30+ гачи-клипов.
  Логика: сначала ищем подходящий клип по смыслу ответа,
  если не нашли — XTTS с голосом Билли, fallback Silero/pyttsx3.
  """

  import os, logging, threading, queue, re, random
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

  _CLIPS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "voice")

  # ── Полная библиотека гачи-клипов Билли ──────────────────────────────────────
  # Формат: "ключевое слово/фраза" → "файл.mp3"
  # Ключи — на английском (Билли говорил по-английски), русские — для контекста
  BILLY_CLIPS = {
      # Приветствие / готовность
      "are you ready":         "are_you_ready.mp3",
      "let's go":              "lets_go.mp3",
      "let me go":             "lets_go.mp3",
      "right here right now":  "right_here_right_now.mp3",
      "come on":               "come_on.mp3",

      # Одобрение / успех
      "yeah buddy":            "yeah_buddy.mp3",
      "that's right":          "thats_right.mp3",
      "good job":              "good_job.mp3",
      "well done":             "good_job.mp3",
      "nice":                  "nice.mp3",
      "beautiful":             "beautiful.mp3",
      "oh yeah":               "oh_yeah.mp3",
      "hell yeah":             "hell_yeah.mp3",
      "i like it":             "i_like_it.mp3",

      # Мотивация / усилие
      "no pain no gain":       "no_pain_no_gain.mp3",
      "no pain, no gain":      "no_pain_no_gain.mp3",
      "wrestle with the best": "wrestle_with_the_best.mp3",
      "work it":               "work_it.mp3",
      "push it":               "push_it.mp3",
      "feel the burn":         "feel_the_burn.mp3",

      # Идентичность
      "i'm your man":          "im_your_man.mp3",
      "it's a man's world":    "mans_world.mp3",
      "billy":                 "im_your_man.mp3",

      # Эмоции
      "oh my god":             "oh_my_god.mp3",
      "oh god":                "oh_my_god.mp3",
      "wow":                   "wow.mp3",
      "incredible":            "incredible.mp3",
      "amazing":               "incredible.mp3",
      "unbelievable":          "unbelievable.mp3",

      # Разное
      "take it easy":          "take_it_easy.mp3",
      "relax":                 "take_it_easy.mp3",
      "calm down":             "take_it_easy.mp3",
      "don't stop":            "dont_stop.mp3",
      "never give up":         "no_pain_no_gain.mp3",
      "do it":                 "do_it.mp3",

      # Русские триггеры → английские клипы
      "исполняю":              "lets_go.mp3",
      "готово":                "yeah_buddy.mp3",
      "сделано":               "yeah_buddy.mp3",
      "отлично":               "nice.mp3",
      "вперёд":                "lets_go.mp3",
      "давай":                 "come_on.mp3",
      "молодец":               "good_job.mp3",
      "понял":                 "thats_right.mp3",
      "хорошо":                "nice.mp3",
      "ошибка":                "oh_my_god.mp3",
      "проблема":              "oh_my_god.mp3",
      "невероятно":            "incredible.mp3",
  }

  # Контекстный маппинг: если в ответе есть смысловой блок → играем клип
  CONTEXT_CLIPS = {
      r"(готов|сделал|выполн|закончил|успешно|работает)": "yeah_buddy.mp3",
      r"(ошибка|упало|сломал|не работает|проблема|баг)":   "oh_my_god.mp3",
      r"(привет|здравств|добро пожаловать)":               "are_you_ready.mp3",
      r"(давай|начнём|поехали|вперёд)":                    "lets_go.mp3",
      r"(отлично|молодец|хорошо|правильно)":               "good_job.mp3",
      r"(невероятно|удивительно|вот это да)":              "incredible.mp3",
      r"(подожди|секунд|минут|думаю)":                     "take_it_easy.mp3",
  }

  # Клипы для случайного использования (разнообразие)
  RANDOM_POOL = ["come_on.mp3", "lets_go.mp3", "yeah_buddy.mp3", "nice.mp3", "thats_right.mp3"]

  # ── Скачивание клипов с Archive.org ──────────────────────────────────────────
  # Коллекция: https://archive.org/details/billy-herrington-voice-pack
  BILLY_ARCHIVE_BASE = "https://archive.org/download/billy-herrington-voice-pack"
  BILLY_CLIPS_DOWNLOAD = {
      "are_you_ready.mp3":        f"{BILLY_ARCHIVE_BASE}/are_you_ready.mp3",
      "lets_go.mp3":              f"{BILLY_ARCHIVE_BASE}/lets_go.mp3",
      "no_pain_no_gain.mp3":      f"{BILLY_ARCHIVE_BASE}/no_pain_no_gain.mp3",
      "yeah_buddy.mp3":           f"{BILLY_ARCHIVE_BASE}/yeah_buddy.mp3",
      "come_on.mp3":              f"{BILLY_ARCHIVE_BASE}/come_on.mp3",
      "right_here_right_now.mp3": f"{BILLY_ARCHIVE_BASE}/right_here_right_now.mp3",
      "im_your_man.mp3":          f"{BILLY_ARCHIVE_BASE}/im_your_man.mp3",
      "mans_world.mp3":           f"{BILLY_ARCHIVE_BASE}/mans_world.mp3",
      "wrestle_with_the_best.mp3":f"{BILLY_ARCHIVE_BASE}/wrestle_with_the_best.mp3",
      "good_job.mp3":             f"{BILLY_ARCHIVE_BASE}/good_job.mp3",
      "oh_my_god.mp3":            f"{BILLY_ARCHIVE_BASE}/oh_my_god.mp3",
      "incredible.mp3":           f"{BILLY_ARCHIVE_BASE}/incredible.mp3",
      "thats_right.mp3":          f"{BILLY_ARCHIVE_BASE}/thats_right.mp3",
      "nice.mp3":                 f"{BILLY_ARCHIVE_BASE}/nice.mp3",
      "oh_yeah.mp3":              f"{BILLY_ARCHIVE_BASE}/oh_yeah.mp3",
      "take_it_easy.mp3":         f"{BILLY_ARCHIVE_BASE}/take_it_easy.mp3",
      "do_it.mp3":                f"{BILLY_ARCHIVE_BASE}/do_it.mp3",
      "dont_stop.mp3":            f"{BILLY_ARCHIVE_BASE}/dont_stop.mp3",
      "hell_yeah.mp3":            f"{BILLY_ARCHIVE_BASE}/hell_yeah.mp3",
      "wow.mp3":                  f"{BILLY_ARCHIVE_BASE}/wow.mp3",
      "beautiful.mp3":            f"{BILLY_ARCHIVE_BASE}/beautiful.mp3",
      "unbelievable.mp3":         f"{BILLY_ARCHIVE_BASE}/unbelievable.mp3",
      "work_it.mp3":              f"{BILLY_ARCHIVE_BASE}/work_it.mp3",
      "push_it.mp3":              f"{BILLY_ARCHIVE_BASE}/push_it.mp3",
      "i_like_it.mp3":            f"{BILLY_ARCHIVE_BASE}/i_like_it.mp3",
      "feel_the_burn.mp3":        f"{BILLY_ARCHIVE_BASE}/feel_the_burn.mp3",
      "oh_yeah.mp3":              f"{BILLY_ARCHIVE_BASE}/oh_yeah.mp3",
  }

  _BILLY_REF_PATH = os.path.join(_CLIPS_DIR, "reference", "billy_ref.wav")


  def _play_clip(filename: str) -> bool:
      path = os.path.join(_CLIPS_DIR, filename)
      if not os.path.exists(path):
          return False
      try:
          import sounddevice as sd
          import soundfile as sf
          data, sr = sf.read(path, dtype="float32")
          sd.play(data, sr); sd.wait()
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
      """Ищет подходящий гачи-клип по тексту ответа. Два прохода: точные фразы → контекст."""
      text_lower = text.lower()

      # Проход 1: точные фразы из словаря
      for phrase, filename in BILLY_CLIPS.items():
          if phrase in text_lower:
              if _play_clip(filename):
                  logger.debug(f"Клип по фразе '{phrase}': {filename}")
                  return True

      # Проход 2: контекстный (regex по смыслу)
      for pattern, filename in CONTEXT_CLIPS.items():
          if re.search(pattern, text_lower, re.I):
              if _play_clip(filename):
                  logger.debug(f"Клип по контексту '{pattern}': {filename}")
                  return True

      return False


  def _try_random_clip() -> bool:
      """Играет случайный клип из пула (для разнообразия)."""
      available = [f for f in RANDOM_POOL if os.path.exists(os.path.join(_CLIPS_DIR, f))]
      if not available:
          return False
      return _play_clip(random.choice(available))


  # ── XTTS-v2 — клонирование голоса Билли ──────────────────────────────────────
  def _ensure_billy_reference() -> Optional[str]:
      if os.path.exists(_BILLY_REF_PATH) and os.path.getsize(_BILLY_REF_PATH) > 1000:
          return _BILLY_REF_PATH
      os.makedirs(os.path.dirname(_BILLY_REF_PATH), exist_ok=True)

      # Пробуем конвертировать любой .mp3 клип в .wav для XTTS
      for clip in ["are_you_ready.mp3", "lets_go.mp3", "yeah_buddy.mp3", "come_on.mp3"]:
          src = os.path.join(_CLIPS_DIR, clip)
          if not os.path.exists(src):
              continue
          try:
              import soundfile as sf
              import numpy as np
              # Используем soundfile для конвертации (работает с mp3 через libsndfile)
              try:
                  data, sr = sf.read(src, dtype="float32")
                  sf.write(_BILLY_REF_PATH, data, sr)
                  logger.info(f"Референс создан из {clip}")
                  return _BILLY_REF_PATH
              except Exception:
                  pass
          except ImportError:
              pass

      # Последний вариант — скачиваем напрямую
      import urllib.request
      wav_urls = [
          "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds/lets_go.mp3",
          "https://archive.org/download/gachi-sounds-pack/billy_ready.mp3",
      ]
      for url in wav_urls:
          try:
              req = urllib.request.Request(url, headers={"User-Agent": "AnikiBuddy/3.2"})
              with urllib.request.urlopen(req, timeout=15) as r:
                  raw = r.read()
              if len(raw) > 5000:
                  with open(_BILLY_REF_PATH.replace(".wav", "_raw.mp3"), "wb") as f:
                      f.write(raw)
                  logger.info("Референс-аудио Билли скачан")
                  return _BILLY_REF_PATH.replace(".wav", "_raw.mp3")
          except Exception as e:
              logger.debug(f"Референс-URL недоступен: {e}")
      return None


  def _load_xtts():
      global _xtts_model, _xtts_loaded
      with _tts_lock:
          if _xtts_loaded:
              return _xtts_model
          try:
              from TTS.api import TTS as CoquiTTS
              ref = _ensure_billy_reference()
              if not ref:
                  logger.info("XTTS: нет референса Билли — пропускаем")
                  return None
              model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")
              model.to("cpu")
              _xtts_model  = (model, ref)
              _xtts_loaded = True
              logger.info("XTTS-v2 с голосом Билли загружен ✓")
              return _xtts_model
          except Exception as e:
              logger.debug(f"XTTS недоступен: {e}")
              return None


  def _speak_xtts(text: str, ref_path: str) -> bool:
      try:
          from TTS.api import TTS as CoquiTTS
          import sounddevice as sd
          import soundfile as sf
          import tempfile
          loaded = _load_xtts()
          if not loaded:
              return False
          model, ref = loaded
          with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
              tmp = f.name
          model.tts_to_file(
              text=text, speaker_wav=ref,
              language="ru", file_path=tmp,
          )
          data, sr = sf.read(tmp, dtype="float32")
          sd.play(data, sr); sd.wait()
          import os; os.unlink(tmp)
          return True
      except Exception as e:
          logger.debug(f"XTTS speak error: {e}")
          return False


  # ── Silero TTS (основной синтез) ──────────────────────────────────────────────
  def _load_silero():
      global _silero_model, _silero_loaded
      with _tts_lock:
          if _silero_loaded:
              return _silero_model
          try:
              import torch
              models_dir = os.path.join(
                  os.path.dirname(os.path.dirname(__file__)), "data", "models", "silero_tts"
              )
              os.makedirs(models_dir, exist_ok=True)
              torch.hub.set_dir(models_dir)
              model, _ = torch.hub.load(
                  "snakers4/silero-models",
                  "silero_tts", language="ru",
                  speaker=SILERO_MODEL_ID,
                  trust_repo=True, verbose=False,
              )
              model.to(torch.device("cpu"))
              _silero_model  = model
              _silero_loaded = True
              logger.info("Silero TTS загружен ✓")
              return model
          except Exception as e:
              logger.debug(f"Silero TTS недоступен: {e}")
              return None


  def _speak_silero(text: str) -> bool:
      model = _load_silero()
      if not model:
          return False
      try:
          import torch
          import sounddevice as sd
          audio = model.apply_tts(
              text=text, speaker=SILERO_SPEAKER,
              sample_rate=_sample_rate,
          )
          sd.play(audio.numpy(), _sample_rate); sd.wait()
          return True
      except Exception as e:
          logger.debug(f"Silero TTS speak: {e}")
          return False


  def _speak_pyttsx3(text: str) -> bool:
      try:
          import pyttsx3
          engine = pyttsx3.init()
          # Попробуем выбрать мужской голос
          voices = engine.getProperty("voices")
          for v in voices:
              if any(k in v.name.lower() for k in ["male", "david", "mark"]):
                  engine.setProperty("voice", v.id); break
          engine.setProperty("rate", 165)
          engine.setProperty("volume", 1.0)
          engine.say(text)
          engine.runAndWait()
          return True
      except Exception as e:
          logger.debug(f"pyttsx3: {e}")
          return False


  # ── Публичный API ─────────────────────────────────────────────────────────────
  def speak(text: str, use_clips: bool = True) -> bool:
      """
      Воспроизводит текст.
      Приоритет: гачи-клип → XTTS (голос Билли) → Silero → pyttsx3.
      """
      if not text or not text.strip():
          return False

      # 1. Гачи-клип по смыслу текста
      if use_clips and _try_billy_clip(text):
          return True

      # 2. XTTS с голосом Билли (если доступен)
      loaded = _load_xtts()
      if loaded:
          model, ref = loaded
          if _speak_xtts(text, ref):
              return True

      # 3. Silero TTS
      if _speak_silero(text):
          return True

      # 4. pyttsx3 системный
      return _speak_pyttsx3(text)


  def get_tts_backend() -> str:
      if os.path.exists(_BILLY_REF_PATH):
          try:
              from TTS.api import TTS
              return "xtts_billy"
          except ImportError:
              pass
      clips = [f for f in BILLY_CLIPS.values() if os.path.exists(os.path.join(_CLIPS_DIR, f))]
      if clips:
          return f"clips({len(clips)})"
      try:
          import torch; _load_silero(); return "silero" if _silero_loaded else "pyttsx3"
      except Exception:
          return "pyttsx3"


  class StreamTTS:
      """Потоковый TTS для стриминга токенов от ИИ."""
      def __init__(self, use_clips: bool = True):
          self._q: queue.Queue = queue.Queue()
          self._thread: Optional[threading.Thread] = None
          self._stop = threading.Event()
          self.use_clips = use_clips

      def start(self):
          self._stop.clear()
          self._thread = threading.Thread(target=self._worker, daemon=True)
          self._thread.start()

      def push(self, text: str):
          if text.strip():
              self._q.put(text)

      def stop(self):
          self._stop.set()
          self._q.put(None)
          if self._thread:
              self._thread.join(timeout=5)

      def __del__(self):
          self.stop()

      def _worker(self):
          buf = ""
          while not self._stop.is_set():
              try:
                  chunk = self._q.get(timeout=0.1)
                  if chunk is None:
                      break
                  buf += chunk
                  if any(p in buf for p in ".!?\n"):
                      speak(buf.strip(), use_clips=self.use_clips)
                      buf = ""
              except queue.Empty:
                  if buf.strip():
                      speak(buf.strip(), use_clips=self.use_clips)
                      buf = ""
  