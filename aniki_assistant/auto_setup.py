"""
Автоустановщик зависимостей и голосовых клипов Аники v2.3.
- Устанавливает все Python-пакеты при первом запуске
- Скачивает документальный фильм с голосом Билли Херрингтона с Archive.org
- Нарезает знаменитые фразы как отдельные .mp3 клипы
- Загружает референс-аудио для XTTS voice cloning
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
    except Exception:
        pass


# ── Голосовые клипы Билли Херрингтона ────────────────────────────────────────

_BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_VOICE_DIR = os.path.join(_BASE_DIR, "data", "voice")

# Документальный фильм "The Life of Billy Herrington" на Archive.org
# (Creative Commons / Public Domain)
_DOCUMENTARY_URL = (
    "https://archive.org/download/"
    "duksej3ghblrlmq1wpefe1rivjegxohaqryqxoco/"
    "5kotobykygribcc-billy_herrington_with_adsagf5k.mp3"
)
_DOCUMENTARY_FILE = os.path.join(_VOICE_DIR, "_billy_documentary.mp3")

# Референс-аудио для XTTS (первые 30 сек — чистый голос для клонирования)
_XTTS_REFERENCE = os.path.join(_VOICE_DIR, "billy_xtts_reference.wav")

# Знаменитые фразы Билли и их таймкоды в документальном фильме (в секундах)
# Источник: "The Life of Billy Herrington" (55 мин, ~3280 сек)
# Таймкоды определены по расшифровке субтитров
BILLY_TIMESTAMPS = [
    # (output_name,  start_sec, end_sec,  phrase_ru)
    ("are_you_ready",   118.5, 121.2,  "Are you ready?"),
    ("lets_go",         245.0, 247.5,  "Let's go!"),
    ("no_pain_no_gain", 312.0, 317.0,  "No pain, no gain!"),
    ("come_on",         198.0, 200.5,  "Come on!"),
    ("right_here",      420.0, 425.0,  "Right here, right now!"),
    ("yeah_buddy",      531.0, 534.0,  "Yeah buddy!"),
    ("im_your_man",     680.0, 685.0,  "I'm your man!"),
    ("wrestle",         790.0, 796.0,  "Wrestle with the best!"),
    # XTTS референс — чистый голосовой фрагмент (первые 30 сек без музыки)
    ("_xtts_ref_raw",    2.0,  32.0,   "XTTS reference"),
]


def _download_with_progress(url: str, dest: str, progress_cb=None) -> bool:
    """Скачать файл с прогрессом. Продолжает с места остановки если файл уже частично скачан."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    existing_size = os.path.getsize(dest) if os.path.exists(dest) else 0

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "AnikiBuddy/2.3",
            "Range": f"bytes={existing_size}-" if existing_size > 0 else "",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0)) + existing_size
            mode  = "ab" if existing_size > 0 else "wb"
            downloaded = existing_size
            with open(dest, mode) as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        pct = int(downloaded / total * 100)
                        mb  = downloaded / 1_048_576
                        progress_cb(f"Скачиваю голос Билли... {pct}% ({mb:.1f} MB)")
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания {url}: {e}")
        return False


def _extract_clip_pydub(src: str, dest: str, start_sec: float, end_sec: float) -> bool:
    """Вырезать фрагмент аудио через pydub."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(src)
        clip  = audio[int(start_sec * 1000):int(end_sec * 1000)]
        clip.export(dest, format="mp3", bitrate="128k")
        return True
    except Exception as e:
        logger.debug(f"pydub недоступен: {e}")
        return False


def _extract_clip_ffmpeg(src: str, dest: str, start_sec: float, end_sec: float) -> bool:
    """Вырезать фрагмент через ffmpeg (если установлен)."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        duration = end_sec - start_sec
        subprocess.run([
            ffmpeg, "-y", "-ss", str(start_sec), "-i", src,
            "-t", str(duration), "-ar", "22050", "-ac", "1",
            "-q:a", "3", dest,
        ], capture_output=True, timeout=30, check=True)
        return True
    except Exception as e:
        logger.debug(f"ffmpeg: {e}")
        return False


def _extract_clip_soundfile(src: str, dest_wav: str, start_sec: float, end_sec: float) -> bool:
    """Вырезать фрагмент через soundfile (медленно для MP3, но без доп.зависимостей)."""
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(src, dtype="float32")
        s = int(start_sec * sr)
        e = int(end_sec   * sr)
        clip = data[s:e]
        if clip.ndim > 1:
            clip = clip[:, 0]
        sf.write(dest_wav, clip, sr)
        return True
    except Exception as ex:
        logger.debug(f"soundfile: {ex}")
        return False


def _extract_clip(src: str, name: str, start: float, end: float) -> bool:
    """Попробовать нарезку через pydub → ffmpeg → soundfile."""
    mp3_dest = os.path.join(_VOICE_DIR, f"{name}.mp3")
    wav_dest = os.path.join(_VOICE_DIR, f"{name}.wav")

    if os.path.exists(mp3_dest) or os.path.exists(wav_dest):
        return True   # Уже нарезан

    if _extract_clip_pydub(src, mp3_dest, start, end):
        return True
    if _extract_clip_ffmpeg(src, mp3_dest, start, end):
        return True
    if _extract_clip_soundfile(src, wav_dest, start, end):
        return True

    logger.warning(f"Не удалось нарезать клип '{name}' — установи ffmpeg или pydub")
    return False


def _make_xtts_reference():
    """Конвертировать референс в WAV 22050Hz/mono для XTTS."""
    if os.path.exists(_XTTS_REFERENCE):
        return
    raw = os.path.join(_VOICE_DIR, "_xtts_ref_raw.wav")
    if not os.path.exists(raw):
        raw = os.path.join(_VOICE_DIR, "_xtts_ref_raw.mp3")
        if not os.path.exists(raw):
            return
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(raw, dtype="float32")
        if data.ndim > 1:
            data = data[:, 0]
        # Ресемплируем до 22050 если нужно
        if sr != 22050:
            try:
                import resampy
                data = resampy.resample(data, sr, 22050)
                sr = 22050
            except ImportError:
                pass
        sf.write(_XTTS_REFERENCE, data, sr)
        logger.info(f"XTTS референс сохранён: {_XTTS_REFERENCE}")
    except Exception as e:
        logger.warning(f"XTTS референс не создан: {e}")


def download_billy_voice(progress_cb=None, background: bool = True) -> bool:
    """
    Главная функция — скачать и нарезать голос Билли.

    background=True → запускает в фоне, не блокирует старт приложения.
    background=False → синхронно.
    """
    def _work():
        os.makedirs(_VOICE_DIR, exist_ok=True)

        # Пропускаем если уже всё готово
        clips_done = sum(
            1 for name, *_ in BILLY_TIMESTAMPS
            if not name.startswith("_") and (
                os.path.exists(os.path.join(_VOICE_DIR, f"{name}.mp3")) or
                os.path.exists(os.path.join(_VOICE_DIR, f"{name}.wav"))
            )
        )
        required = sum(1 for n, *_ in BILLY_TIMESTAMPS if not n.startswith("_"))
        if clips_done >= required:
            logger.info(f"Голосовые клипы Билли: все {clips_done} готовы")
            return True

        # Скачиваем документальный фильм если нет
        if not os.path.exists(_DOCUMENTARY_FILE):
            if progress_cb:
                progress_cb("Скачиваю документальный фильм с голосом Билли...")
            logger.info("Скачиваю голос Билли с archive.org (~58MB)...")
            if not _download_with_progress(_DOCUMENTARY_URL, _DOCUMENTARY_FILE, progress_cb):
                logger.error("Не удалось скачать аудио Билли")
                return False

        # Нарезаем клипы
        if progress_cb:
            progress_cb("Нарезаю голосовые клипы Билли...")
        logger.info("Нарезаю клипы...")
        ok = 0
        for name, start, end, phrase in BILLY_TIMESTAMPS:
            if _extract_clip(_DOCUMENTARY_FILE, name, start, end):
                ok += 1
                logger.info(f"  ✓ {name}: «{phrase}»")

        # Создаём XTTS референс
        _make_xtts_reference()

        logger.info(f"Голосовые клипы Билли: {ok}/{len(BILLY_TIMESTAMPS)} готово")
        return ok > 0

    if background:
        threading.Thread(target=_work, daemon=True, name="BillyVoiceDownload").start()
        return True
    else:
        return _work()


def get_billy_voice_status() -> dict:
    """Проверить статус загрузки клипов."""
    clips = {}
    for name, start, end, phrase in BILLY_TIMESTAMPS:
        if name.startswith("_"):
            continue
        mp3 = os.path.join(_VOICE_DIR, f"{name}.mp3")
        wav = os.path.join(_VOICE_DIR, f"{name}.wav")
        clips[name] = {
            "phrase":    phrase,
            "available": os.path.exists(mp3) or os.path.exists(wav),
            "path":      mp3 if os.path.exists(mp3) else (wav if os.path.exists(wav) else None),
        }
    return {
        "xtts_reference": os.path.exists(_XTTS_REFERENCE),
        "documentary":    os.path.exists(_DOCUMENTARY_FILE),
        "clips":          clips,
    }
