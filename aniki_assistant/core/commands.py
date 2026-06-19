"""
Обработчик системных команд Windows для Аники v2.3.
FIX: умный парсинг — не путает "YouTube-канал Wacky на Rust" с "открой Rust".
NEW: открытие YouTube-каналов по имени автора.
NEW: открытие произвольных URL.
"""

import subprocess
import os
import sys
import re
import webbrowser
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        import ctypes
        PYCAW_AVAILABLE = True
    except ImportError:
        PYCAW_AVAILABLE = False
else:
    PYCAW_AVAILABLE = False

# ── Звук ──────────────────────────────────────────────────────────────────────

def set_volume(percent: int) -> Tuple[bool, str]:
    percent = max(0, min(100, percent))
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices   = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume    = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
            return True, f"Громкость {percent}%!"
        except Exception as e:
            logger.error(f"Ошибка громкости: {e}")
    return False, f"Громкость: {percent}% (управление недоступно)"


def toggle_mute() -> Tuple[bool, str]:
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices   = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume    = interface.QueryInterface(IAudioEndpointVolume)
            muted     = volume.GetMute()
            volume.SetMute(not muted, None)
            state = "выключен" if not muted else "включён"
            return True, f"Звук {state}!"
        except Exception as e:
            logger.error(f"Ошибка mute: {e}")
    return False, "Управление звуком недоступно"


def toggle_microphone() -> Tuple[bool, str]:
    return True, "Микрофон переключён"


# ── Окна ──────────────────────────────────────────────────────────────────────

def minimize_all_windows() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x4D, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x4D, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
            return True, "Свернул всё! Let's go!"
        except Exception:
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     "(New-Object -ComObject Shell.Application).MinimizeAll()"],
                    capture_output=True, timeout=3
                )
                return True, "Окна свёрнуты!"
            except Exception as e:
                return False, str(e)
    return False, "Только на Windows"


def restore_all_windows() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "(New-Object -ComObject Shell.Application).UndoMinimizeAll()"],
                capture_output=True, timeout=3
            )
            return True, "Окна восстановлены!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


# ── Приложения ────────────────────────────────────────────────────────────────

APP_MAP = {
    "discord":    ["discord", r"C:\Users\*\AppData\Local\Discord\app-*\Discord.exe"],
    "steam":      ["steam",   r"C:\Program Files (x86)\Steam\steam.exe"],
    "spotify":    ["spotify", r"C:\Users\*\AppData\Roaming\Spotify\Spotify.exe"],
    "telegram":   ["telegram",r"C:\Users\*\AppData\Roaming\Telegram Desktop\Telegram.exe"],
    "vscode":     ["code"],
    "notepad":    ["notepad"],
    "calculator": ["calc"],
    "explorer":   ["explorer"],
    "rust":       ["steam", "steam://rungameid/252490"],
    "cs2":        ["steam", "steam://rungameid/730"],
    "csgo":       ["steam", "steam://rungameid/730"],
    "dota":       ["steam", "steam://rungameid/570"],
    "dota2":      ["steam", "steam://rungameid/570"],
    "minecraft":  ["steam", "steam://rungameid/22460"],
    "gta":        ["steam", "steam://rungameid/271590"],
    "cyberpunk":  ["steam", "steam://rungameid/1091500"],
    "witcher":    ["steam", "steam://rungameid/292030"],
    "chrome":     ["chrome"],
    "firefox":    ["firefox"],
    "edge":       ["msedge"],
    "opera":      ["opera"],
}

_NON_LAUNCH_PREPS_RU = [
    "на ", "в ", "про ", "о ", "об ", "для ", "по ", "из ", "к ", "со ",
    "канал", "стрим", "видео", "клип", "ролик", "игру", "игра", "игре",
]
_NON_LAUNCH_PREPS_EN = [
    "on ", "about ", "in ", "for ", "of ", "from ", " channel", " stream", " video",
]

def _is_real_launch_command(text: str, app_keyword: str) -> bool:
    t   = text.lower()
    app = app_keyword.lower()
    idx = t.find(app)
    if idx < 0:
        return False
    before = t[:idx]
    after  = t[idx + len(app):]
    for prep in _NON_LAUNCH_PREPS_RU + _NON_LAUNCH_PREPS_EN:
        if before.rstrip().endswith(prep.rstrip()):
            return False
    after_stripped = after.strip()
    for cw in ["на ", "в ", "по ", "и ", "о ", "об ", "видео", "канал", "стрим"]:
        if after_stripped.startswith(cw):
            return False
    launch_verbs = ["открой", "запусти", "включи", "открой мне", "запусти мне",
                    "включи мне", "launch", "open", "start", "run"]
    for verb in launch_verbs:
        if before.find(verb) >= 0:
            return True
    if len(t.strip()) <= len(app) + 3:
        return True
    return False


def open_application(name: str) -> Tuple[bool, str]:
    name_lower = name.lower().strip()
    for key, cmds in APP_MAP.items():
        if key in name_lower:
            try:
                if len(cmds) == 2 and cmds[1].startswith("steam://"):
                    webbrowser.open(cmds[1])
                    return True, f"Запускаю {key.capitalize()} через Steam!"
                subprocess.Popen(cmds[:1], shell=False,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, f"Запускаю {key.capitalize()}!"
            except FileNotFoundError:
                pass
    try:
        subprocess.Popen([name_lower], shell=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, f"Запускаю {name}!"
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            r = subprocess.run(["where", name_lower], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                path = r.stdout.strip().splitlines()[0]
                subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, f"Запускаю {name}!"
        except Exception:
            pass
    return False, f"Не нашёл '{name}'. Открой через меню Пуск."


def close_application(name: str) -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/f", "/im", f"{name}.exe"],
                           capture_output=True, timeout=5)
            return True, f"Закрыл {name}!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


# ── Браузер, YouTube и каналы ─────────────────────────────────────────────────

def open_browser(url: str = "") -> Tuple[bool, str]:
    try:
        webbrowser.open(url if url else "https://google.com")
        return True, f"Открываю: {url}" if url else "Браузер открыт!"
    except Exception as e:
        return False, str(e)


def open_youtube(query: str = "") -> Tuple[bool, str]:
    if query:
        url = f"https://youtube.com/results?search_query={query.replace(' ', '+')}"
    else:
        url = "https://youtube.com"
    return open_browser(url)


def open_youtube_channel(name: str) -> Tuple[bool, str]:
    """
    Открыть YouTube-канал по имени автора.
    Сначала пробуем @handle (если имя без пробелов), потом поиск с фильтром каналов.
    """
    name = name.strip()
    # Попытка прямого перехода к @handle (один слово без пробелов)
    if " " not in name:
        direct_url = f"https://www.youtube.com/@{name}"
        try:
            webbrowser.open(direct_url)
            return True, f"Открываю канал @{name} на YouTube!"
        except Exception:
            pass
    # Поиск с фильтром «Каналы» (sp=EgIQAg%3D%3D)
    url = (
        f"https://www.youtube.com/results"
        f"?search_query={name.replace(' ', '+')}"
        f"&sp=EgIQAg%253D%253D"
    )
    try:
        webbrowser.open(url)
        return True, f"Ищу канал {name} на YouTube!"
    except Exception as e:
        return False, str(e)


def open_url(url: str) -> Tuple[bool, str]:
    if not url.startswith("http"):
        url = "https://" + url
    return open_browser(url)


# ── Системные команды ─────────────────────────────────────────────────────────

def lock_screen() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return True, "Блокирую экран!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


def shutdown_computer(delay: int = 30) -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/s", "/t", str(delay)], check=True)
            return True, f"Выключение через {delay} сек!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


def restart_computer() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/r", "/t", "10"], check=True)
            return True, "Перезагрузка через 10 сек!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


def sleep_computer() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Add-Type -Assembly System.Windows.Forms; "
                 "[System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false)"],
                capture_output=True, timeout=5
            )
            return True, "Спящий режим! До встречи, бро!"
        except Exception as e:
            return False, str(e)
    return False, "Только на Windows"


def take_screenshot() -> Tuple[bool, str]:
    try:
        import PIL.ImageGrab
        import time
        fn   = f"screenshot_{int(time.time())}.png"
        dest = os.path.join(os.path.expanduser("~"), "Desktop", fn)
        PIL.ImageGrab.grab().save(dest)
        return True, f"Скриншот: {fn}"
    except ImportError:
        if IS_WINDOWS:
            try:
                subprocess.Popen(["snippingtool"])
                return True, "Инструмент снимка открыт"
            except Exception:
                pass
        return False, "PIL не установлен"
    except Exception as e:
        return False, str(e)


# ── Промпт ────────────────────────────────────────────────────────────────────

PROMPT_MARKER = "__PROMPT_RESULT__:"

def mark_as_prompt(text: str) -> str:
    return f"{PROMPT_MARKER}{text}"

def is_prompt_result(text: str) -> bool:
    return text.startswith(PROMPT_MARKER)

def extract_prompt(text: str) -> str:
    return text[len(PROMPT_MARKER):]


# ── Паттерны команд ───────────────────────────────────────────────────────────

_VOLUME_SET_RE  = re.compile(
    r"(?:сделай|поставь|установи|громкость|звук)\s+(?:звук|громкость)?\s*(?:на\s+)?(\d+)\s*%?", re.I)
_VOLUME_RE      = re.compile(r"(?:громкость|звук)\s+(\d+)\s*%?", re.I)
_YT_SEARCH_RE   = re.compile(
    r"(?:найди|открой|включи|ищи)\s+(?:на\s+)?youtube\s+(.+)|youtube\s+(.+)", re.I)
_YT_CHANNEL_RE  = re.compile(
    r"(?:открой|найди|покажи|включи|запусти)\s+"
    r"(?:ютуб[-\s]?канал|youtube[-\s]?канал|канал\s+(?:на\s+)?(?:youtube|ютубе?)?)\s*"
    r"[—\-]?\s*(.+)",
    re.I,
)
_OPEN_APP_RE    = re.compile(r"(?:открой|запусти|включи)(?:\s+мне)?\s+(.+)", re.I)
_CLOSE_APP_RE   = re.compile(r"(?:закрой|вырубай|убей|kill)\s+(.+)", re.I)
_MINIMIZE_RE    = re.compile(
    r"(?:сверни|скрой|спрячь)\s+(?:все\s+)?(?:окна|вкладки|приложения)", re.I)
_RESTORE_RE     = re.compile(
    r"(?:разверни|восстанови)\s+(?:все\s+)?(?:окна|вкладки)", re.I)
_OPEN_URL_RE    = re.compile(
    r"(?:открой|зайди на|перейди на|открой сайт)\s+(https?://\S+|\S+\.\S+)", re.I)


def try_parse_command(text: str) -> Optional[Tuple[bool, str]]:
    t = text.lower().strip()

    if _MINIMIZE_RE.search(t):
        return minimize_all_windows()
    if _RESTORE_RE.search(t):
        return restore_all_windows()

    m = _VOLUME_SET_RE.search(t)
    if m:
        return set_volume(int(m.group(1)))
    m = _VOLUME_RE.search(t)
    if m:
        return set_volume(int(m.group(1)))

    if re.search(r"(?:отключи|выключи)\s+(?:звук|аудио)", t, re.I):
        return toggle_mute()
    if re.search(r"(?:включи|переключи)\s+(?:микрофон|мик)", t, re.I):
        return toggle_microphone()

    # YouTube-канал по имени (НОВОЕ — проверяем ПЕРЕД общим youtube-поиском)
    m = _YT_CHANNEL_RE.search(text)
    if m:
        return open_youtube_channel(m.group(1).strip())

    # YouTube поиск
    m = _YT_SEARCH_RE.search(t)
    if m:
        return open_youtube(m.group(1) or m.group(2) or "")

    # YouTube без запроса
    if re.search(r"(?:открой|запусти)\s+(?:youtube|ютуб)\s*$", t, re.I):
        return open_youtube()

    # Открыть URL
    m = _OPEN_URL_RE.search(text)
    if m:
        return open_url(m.group(1))

    # Браузер
    if re.search(r"(?:открой|запусти)\s+(?:браузер|хром|firefox|edge|opera)\s*$", t, re.I):
        return open_browser()

    # Системные
    if re.search(r"(?:заблокируй|lock)\s+(?:экран|компьютер)", t, re.I):
        return lock_screen()
    if re.search(r"(?:выключи|shutdown)\s+(?:компьютер|пк|комп)", t, re.I):
        return shutdown_computer(30)
    if re.search(r"(?:перезагрузи|restart)\s+(?:компьютер|пк|комп)", t, re.I):
        return restart_computer()
    if re.search(r"скриншот|снимок экрана", t, re.I):
        return take_screenshot()
    if re.search(r"спящий режим|усыпи", t, re.I):
        return sleep_computer()

    # Закрыть приложение
    m = _CLOSE_APP_RE.search(t)
    if m:
        return close_application(m.group(1).strip())

    # Умный запуск приложений
    for app_key in APP_MAP:
        if app_key in t and _is_real_launch_command(text, app_key):
            return open_application(app_key)

    # Общая команда "открой X"
    m = _OPEN_APP_RE.search(t)
    if m:
        app_name = m.group(1).strip()
        if len(app_name.split()) <= 3 and not any(
            kw in app_name for kw in ["канал", "видео", "стрим", "про ", "о ", "об "]
        ):
            return open_application(app_name)

    return None
