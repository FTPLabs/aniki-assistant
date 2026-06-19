"""
  Автоустановщик Аники v3.2.
  - Скачивает полный пак гачи-клипов Билли Херрингтона
  - Автоматически пуллит лучшую локальную модель через Ollama
  - Устанавливает зависимости (не запускается в frozen .exe)
  """
  import sys, subprocess, os, logging, threading, time, urllib.request, json
  logger = logging.getLogger(__name__)

  REQUIRED = [
      ("PyQt6",    "PyQt6>=6.6.0"),
      ("requests", "requests>=2.31.0"),
      ("numpy",    "numpy>=1.24.0"),
      ("psutil",   "psutil>=5.9.0"),
  ]
  OPTIONAL = [
      ("sounddevice",    "sounddevice>=0.4.6"),
      ("soundfile",      "soundfile>=0.12.1"),
      ("faster_whisper", "faster-whisper>=1.0.0"),
      ("pyttsx3",        "pyttsx3>=2.90"),
      ("pygame",         "pygame>=2.5.0"),
  ]
  TORCH = [
      ("torch",      "torch>=2.1.0 --index-url https://download.pytorch.org/whl/cpu"),
      ("torchaudio", "torchaudio>=2.1.0 --index-url https://download.pytorch.org/whl/cpu"),
  ]
  WIN_ONLY = [
      ("pycaw",    "pycaw>=20230412"),
      ("comtypes", "comtypes>=1.2.0"),
      ("win32api", "pywin32>=306"),
      ("webrtcvad","webrtcvad-wheels>=2.0.10"),
      ("pyaudio",  "pyaudio>=0.2.13"),
  ]

  def _ok(name):
      try: __import__(name); return True
      except ImportError: return False

  def _install(spec, timeout=300):
      if getattr(sys, "frozen", False): return False
      try:
          subprocess.check_call(
              [sys.executable, "-m", "pip", "install", "--quiet",
               "--no-warn-script-location"] + spec.split(),
              timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
          return True
      except Exception as e:
          logger.debug(f"pip install {spec}: {e}")
          return False

  def run(progress_cb=None):
      if getattr(sys, "frozen", False):
          return {"installed": [], "failed": [], "ok": ["(frozen exe)"]}
      result = {"installed": [], "failed": [], "ok": []}
      packages = list(REQUIRED) + list(OPTIONAL) + list(TORCH)
      if sys.platform == "win32": packages += WIN_ONLY
      for name, spec in packages:
          if _ok(name):
              result["ok"].append(name); continue
          if progress_cb: progress_cb(f"Устанавливаю {name}...")
          if _install(spec):
              result["installed"].append(name)
          else:
              result["failed"].append(name)
      return result

  def ensure_ollama_autostart():
      if sys.platform != "win32": return
      try:
          import winreg, shutil
          ollama = shutil.which("ollama")
          if not ollama: return
          key = winreg.OpenKey(
              winreg.HKEY_CURRENT_USER,
              r"Software\Microsoft\Windows\CurrentVersion\Run",
              0, winreg.KEY_SET_VALUE)
          winreg.SetValueEx(key, "OllamaServe", 0, winreg.REG_SZ, f'"{ollama}" serve')
          winreg.CloseKey(key)
          logger.info("Ollama добавлен в автозапуск")
      except Exception as e:
          logger.debug(f"ensure_ollama_autostart: {e}")

  # ── Полный пак гачи-клипов ────────────────────────────────────────────────────
  # Archive.org коллекция Billy Herrington sounds
  _ARCHIVE_BASE = "https://archive.org/download/billy-herrington-voice-pack"
  _FALLBACK_BASE = "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds"

  BILLY_CLIPS_PACK = {
      "are_you_ready.mp3":         [f"{_ARCHIVE_BASE}/are_you_ready.mp3",         f"{_FALLBACK_BASE}/are_you_ready.mp3"],
      "lets_go.mp3":               [f"{_ARCHIVE_BASE}/lets_go.mp3",               f"{_FALLBACK_BASE}/lets_go.mp3"],
      "no_pain_no_gain.mp3":       [f"{_ARCHIVE_BASE}/no_pain_no_gain.mp3",       f"{_FALLBACK_BASE}/no_pain_no_gain.mp3"],
      "yeah_buddy.mp3":            [f"{_ARCHIVE_BASE}/yeah_buddy.mp3",            f"{_FALLBACK_BASE}/yeah_buddy.mp3"],
      "come_on.mp3":               [f"{_ARCHIVE_BASE}/come_on.mp3",               f"{_FALLBACK_BASE}/come_on.mp3"],
      "right_here_right_now.mp3":  [f"{_ARCHIVE_BASE}/right_here_right_now.mp3"],
      "im_your_man.mp3":           [f"{_ARCHIVE_BASE}/im_your_man.mp3"],
      "mans_world.mp3":            [f"{_ARCHIVE_BASE}/mans_world.mp3"],
      "wrestle_with_the_best.mp3": [f"{_ARCHIVE_BASE}/wrestle_with_the_best.mp3"],
      "good_job.mp3":              [f"{_ARCHIVE_BASE}/good_job.mp3"],
      "oh_my_god.mp3":             [f"{_ARCHIVE_BASE}/oh_my_god.mp3"],
      "incredible.mp3":            [f"{_ARCHIVE_BASE}/incredible.mp3"],
      "thats_right.mp3":           [f"{_ARCHIVE_BASE}/thats_right.mp3"],
      "nice.mp3":                  [f"{_ARCHIVE_BASE}/nice.mp3"],
      "oh_yeah.mp3":               [f"{_ARCHIVE_BASE}/oh_yeah.mp3"],
      "take_it_easy.mp3":          [f"{_ARCHIVE_BASE}/take_it_easy.mp3"],
      "do_it.mp3":                 [f"{_ARCHIVE_BASE}/do_it.mp3"],
      "dont_stop.mp3":             [f"{_ARCHIVE_BASE}/dont_stop.mp3"],
      "hell_yeah.mp3":             [f"{_ARCHIVE_BASE}/hell_yeah.mp3"],
      "wow.mp3":                   [f"{_ARCHIVE_BASE}/wow.mp3"],
      "beautiful.mp3":             [f"{_ARCHIVE_BASE}/beautiful.mp3"],
      "unbelievable.mp3":          [f"{_ARCHIVE_BASE}/unbelievable.mp3"],
      "work_it.mp3":               [f"{_ARCHIVE_BASE}/work_it.mp3"],
      "push_it.mp3":               [f"{_ARCHIVE_BASE}/push_it.mp3"],
      "i_like_it.mp3":             [f"{_ARCHIVE_BASE}/i_like_it.mp3"],
      "feel_the_burn.mp3":         [f"{_ARCHIVE_BASE}/feel_the_burn.mp3"],
  }

  def _download_file(urls, dest):
      """Пробует скачать файл по списку URL, возвращает True при успехе."""
      for url in urls:
          try:
              req = urllib.request.Request(url, headers={"User-Agent": "AnikiBuddy/3.2"})
              with urllib.request.urlopen(req, timeout=20) as r:
                  data = r.read()
              if len(data) > 1000:  # минимум 1KB — не пустой файл
                  with open(dest, "wb") as f:
                      f.write(data)
                  return True
          except Exception as e:
              logger.debug(f"Не удалось скачать {url}: {e}")
      return False

  def download_billy_voice(background=True, progress_cb=None):
      """Скачивает полный пак гачи-клипов в background-потоке."""
      def _do():
          voice_dir = os.path.join(os.path.dirname(__file__), "data", "voice")
          os.makedirs(voice_dir, exist_ok=True)
          downloaded = 0
          for filename, urls in BILLY_CLIPS_PACK.items():
              dest = os.path.join(voice_dir, filename)
              if os.path.exists(dest) and os.path.getsize(dest) > 1000:
                  continue
              if progress_cb:
                  progress_cb(f"Скачиваю {filename}...")
              if _download_file(urls, dest):
                  downloaded += 1
                  logger.info(f"Скачан: {filename}")
              else:
                  logger.debug(f"Не удалось: {filename} (все URL недоступны)")
          if downloaded > 0:
              logger.info(f"Гачи-пак: скачано {downloaded} клипов")

      if background:
          threading.Thread(target=_do, daemon=True).start()
      else:
          _do()

  # ── Авто-пулл лучшей модели через Ollama ─────────────────────────────────────
  # Лучшие локальные модели (лучше Mistral), по убыванию качества/размера
  PREFERRED_MODELS = [
      ("qwen2.5:7b",   "Qwen 2.5 7B — лучший выбор для большинства систем"),
      ("llama3.1:8b",  "LLaMA 3.1 8B — Meta, отличный общий ассистент"),
      ("phi4:14b",     "Phi-4 14B — Microsoft, топовый reasoning"),
      ("qwen2.5:3b",   "Qwen 2.5 3B — быстрый, хорош на слабых системах"),
      ("llama3.2:3b",  "LLaMA 3.2 3B — компактный Meta"),
      ("mistral",      "Mistral 7B — fallback"),
  ]
  OLLAMA_BASE = "http://localhost:11434"

  def _get_available_models():
      try:
          with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
              data = json.loads(r.read())
          return [m["name"] for m in data.get("models", [])]
      except Exception:
          return []

  def _pull_model(model_name, progress_cb=None):
      """Пуллит модель через Ollama API (streaming)."""
      import urllib.request
      try:
          req_data = json.dumps({"name": model_name, "stream": True}).encode()
          req = urllib.request.Request(
              f"{OLLAMA_BASE}/api/pull",
              data=req_data,
              headers={"Content-Type": "application/json"},
              method="POST"
          )
          with urllib.request.urlopen(req, timeout=3600) as r:
              for line in r:
                  try:
                      obj = json.loads(line.decode())
                      status = obj.get("status", "")
                      if progress_cb and status:
                          pct = ""
                          if obj.get("total") and obj.get("completed"):
                              pct = f" {round(obj['completed']/obj['total']*100)}%"
                          progress_cb(f"Ollama: {model_name} — {status}{pct}")
                  except Exception:
                      pass
          return True
      except Exception as e:
          logger.debug(f"pull {model_name}: {e}")
          return False

  def ensure_best_model(progress_cb=None, background=True):
      """
      Проверяет доступные модели и пуллит лучшую если нет ни одной из preferred.
      Запускается при старте приложения.
      """
      def _do():
          available = _get_available_models()
          if not available:
              logger.debug("Ollama недоступен — пропускаем")
              return
          # Есть ли уже хорошая модель?
          for model_name, _ in PREFERRED_MODELS[:4]:
              base = model_name.split(":")[0]
              if any(base in a for a in available):
                  logger.info(f"Модель готова: {model_name}")
                  return
          # Нет ни одной — пуллим лучшую для системы
          target = PREFERRED_MODELS[0][0]  # qwen2.5:7b
          if progress_cb:
              progress_cb(f"Скачиваю {target} (лучшая локальная ИИ)...")
          logger.info(f"Ollama: пуллю {target}...")
          _pull_model(target, progress_cb)
          logger.info(f"Ollama: {target} готов")

      if background:
          threading.Thread(target=_do, daemon=True).start()
      else:
          _do()
  