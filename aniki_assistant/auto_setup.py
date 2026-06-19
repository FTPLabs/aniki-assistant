"""
  Автоустановщик Аники v3.2.
  FIX [C4]: убран лишний отступ на уровне модуля.
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
      try:
          __import__(name)
          return True
      except ImportError:
          return False


  def _install(spec, timeout=300):
      if getattr(sys, "frozen", False):
          return False
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
          return {"installed": [], "failed": []}
      installed, failed = [], []
      for name, spec in REQUIRED:
          if not _ok(name):
              if progress_cb:
                  progress_cb(f"Устанавливаю {name}...")
              if _install(spec):
                  installed.append(name)
              else:
                  failed.append(name)
      for name, spec in OPTIONAL:
          if not _ok(name):
              _install(spec)
      if sys.platform == "win32":
          for name, spec in WIN_ONLY:
              if not _ok(name):
                  _install(spec)
      for name, spec in TORCH:
          if not _ok(name):
              if progress_cb:
                  progress_cb(f"Устанавливаю {name} (CPU)...")
              _install(spec, timeout=600)
      return {"installed": installed, "failed": failed}


  def ensure_ollama_autostart():
      """Добавляет Ollama в автозапуск Windows."""
      if sys.platform != "win32":
          return
      try:
          import winreg
          ollama_path = os.path.join(
              os.environ.get("LOCALAPPDATA", ""),
              "Programs", "Ollama", "ollama.exe"
          )
          if not os.path.exists(ollama_path):
              return
          key = winreg.OpenKey(
              winreg.HKEY_CURRENT_USER,
              r"Software\Microsoft\Windows\CurrentVersion\Run",
              0, winreg.KEY_SET_VALUE
          )
          winreg.SetValueEx(key, "Ollama", 0, winreg.REG_SZ, ollama_path)
          winreg.CloseKey(key)
          logger.info("Ollama добавлен в автозапуск")
      except Exception as e:
          logger.debug(f"Ollama autostart: {e}")


  def download_billy_voice(background: bool = False):
      """Скачивает все гачи-клипы Билли в фоне."""
      def _do():
          try:
              from core.tts import download_all_clips
              download_all_clips(silent=True)
          except Exception as e:
              logger.debug(f"Скачивание клипов: {e}")
      if background:
          threading.Thread(target=_do, daemon=True).start()
      else:
          _do()
  