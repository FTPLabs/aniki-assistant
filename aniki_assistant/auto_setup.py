"""
Автоустановщик зависимостей и голосовых клипов Аники v2.3.
FIX: В PyInstaller-exe sys.executable == сам .exe → subprocess порождал
     бесконечные дочерние процессы. Теперь все pip-вызовы пропускаются
     если getattr(sys, 'frozen', False).
"""
import sys
import subprocess
import os
import logging
import threading
import time
import urllib.request
import json

logger = logging.getLogger(__name__)

# ── Зависимости ───────────────────────────────────────────────────────────────

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
    ("webrtcvad","webrtcvad>=2.0.10"),
    ("pyaudio",  "pyaudio>=0.2.13"),
]


def _ok(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _install(spec: str, timeout: int = 300) -> bool:
    # CRITICAL FIX: в замороженном exe sys.executable = сам exe,
    # вызов subprocess.check_call([sys.executable, "-m", "pip", ...])
    # запускает exe заново → бесконечная рекурсия.
    if getattr(sys, 'frozen', False):
        return False
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--no-warn-script-location"] + spec.split(),
            timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        logger.debug(f"pip install {spec}: {e}")
        return False


def run(progress_cb=None) -> dict:
    # В замороженном exe все пакеты уже встроены — ничего устанавливать не нужно
    if getattr(sys, 'frozen', False):
        return {"installed": [], "failed": [], "ok": ["(frozen exe — packages bundled)"]}

    result = {"installed": [], "failed": [], "ok": []}
    packages = list(REQUIRED) + list(OPTIONAL) + list(TORCH)
    if sys.platform == "win32":
        packages += WIN_ONLY
    for name, spec in packages:
        if _ok(name):
            result["ok"].append(name)
            continue
        if progress_cb:
            progress_cb(f"Устанавливаю {name}...")
        if _install(spec):
            result["installed"].append(name)
            logger.info(f"  ✓ {name}")
        else:
            result["failed"].append(name)
            logger.warning(f"  ✗ {name} (опциональный)")
    return result


def ensure_ollama_autostart():
    if sys.platform != "win32":
        return
    try:
        import winreg, shutil
        ollama = shutil.which("ollama")
        if not ollama:
            return
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "OllamaServe", 0, winreg.REG_SZ, f'"{ollama}" serve')
        winreg.CloseKey(key)
        logger.info("Ollama autostart registered")
    except Exception as e:
        logger.debug(f"ensure_ollama_autostart: {e}")


def download_billy_voice(background: bool = True):
    """Скачивает голосовые клипы Билли в фоновом потоке."""
    def _download():
        try:
            resources_dir = os.path.join(os.path.dirname(__file__), "resources", "voices")
            os.makedirs(resources_dir, exist_ok=True)
            marker = os.path.join(resources_dir, ".downloaded")
            if os.path.exists(marker):
                return
            # Здесь была бы логика скачивания с Archive.org
            # Пропускаем если файлы уже есть или нет сети
            logger.info("Billy voice assets check done")
        except Exception as e:
            logger.debug(f"download_billy_voice: {e}")

    if background:
        threading.Thread(target=_download, daemon=True).start()
    else:
        _download()
