"""
Автоустановщик зависимостей Аники v2.2.
Запускается при каждом старте — проверяет и устанавливает всё необходимое.
"""
import sys
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

# (import_name, pip_spec)
REQUIRED = [
    ("PyQt6",    "PyQt6>=6.6.0"),
    ("requests", "requests>=2.31.0"),
    ("numpy",    "numpy>=1.24.0"),
    ("psutil",   "psutil>=5.9.0"),
]

OPTIONAL = [
    ("sounddevice",    "sounddevice>=0.4.6"),
    ("faster_whisper", "faster-whisper>=1.0.0"),
    ("pyttsx3",        "pyttsx3>=2.90"),
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


def _ok(import_name: str) -> bool:
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def _install(pip_spec: str, timeout: int = 300) -> bool:
    try:
        args = [sys.executable, "-m", "pip", "install",
                "--quiet", "--no-warn-script-location"] + pip_spec.split()
        subprocess.check_call(args, timeout=timeout,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.debug(f"pip install {pip_spec}: {e}")
        return False


def run(progress_cb=None) -> dict:
    """
    Проверить и установить все зависимости.
    progress_cb(msg: str) — необязательный колбек прогресса.
    Возвращает {'installed':[], 'failed':[], 'ok':[]}.
    """
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
        logger.info(f"Устанавливаю {name}…")
        if _install(spec):
            result["installed"].append(name)
            logger.info(f"  ✓ {name}")
        else:
            result["failed"].append(name)
            logger.warning(f"  ✗ {name} (опциональный — пропускаю)")

    if result["installed"]:
        logger.info(f"Установлено: {', '.join(result['installed'])}")
    return result


def ensure_ollama_autostart():
    """Добавить Ollama в автозапуск Windows (тихо)."""
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
        logger.info("Ollama добавлен в автозапуск")
    except Exception:
        pass
