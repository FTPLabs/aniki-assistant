"""
  Автоустановщик Аники v3.1.
  FIX [C1]: webrtcvad-wheels вместо webrtcvad (работает на Windows без компилятора).
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
      ("webrtcvad","webrtcvad-wheels>=2.0.10"),  # FIX [C1]: был webrtcvad>=2.0.10
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
              result["installed"].append(name); logger.info(f"  + {name}")
          else:
              result["failed"].append(name); logger.warning(f"  - {name} (опциональный)")
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

  BILLY_CLIPS_URLS = [
      "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds/lets_go.mp3",
      "https://ia802902.us.archive.org/1/items/billy-herrington-gachi-muchi-sounds/are_you_ready.mp3",
  ]

  def download_billy_voice(background=True):
      def _do():
          voice_dir = os.path.join(os.path.dirname(__file__), "data", "voice")
          os.makedirs(voice_dir, exist_ok=True)
          for url in BILLY_CLIPS_URLS:
              fname = url.split("/")[-1]
              dest  = os.path.join(voice_dir, fname)
              if os.path.exists(dest): continue
              try:
                  req = urllib.request.Request(url, headers={"User-Agent": "AnikiBuddy/3.1"})
                  with urllib.request.urlopen(req, timeout=20) as r:
                      with open(dest, "wb") as f: f.write(r.read())
                  logger.info(f"Скачан голосовой клип: {fname}")
              except Exception as e:
                  logger.debug(f"Не удалось скачать {fname}: {e}")
      if background: threading.Thread(target=_do, daemon=True).start()
      else: _do()
  