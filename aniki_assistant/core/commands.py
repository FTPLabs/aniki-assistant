"""
Обработчик системных команд Windows для Аники.
Открывает приложения/игры, сворачивает окна, управляет звуком,
генерирует промпты и многое другое.
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
        logger.warning("pycaw не установлен — управление звуком недоступно")

    try:
        import winreg
        WINREG_AVAILABLE = True
    except ImportError:
        WINREG_AVAILABLE = False
else:
    PYCAW_AVAILABLE = False
    WINREG_AVAILABLE = False


# ── Звук ─────────────────────────────────────────────────────────────────────

def set_volume(percent: int) -> Tuple[bool, str]:
    percent = max(0, min(100, percent))
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
            return True, f"Громкость {percent}%, бро!"
        except Exception as e:
            logger.error(f"Ошибка громкости: {e}")
    if IS_WINDOWS:
        try:
            ps = (f"$obj = New-Object -ComObject WScript.Shell; "
                  f"$wsh = New-Object -ComObject WScript.Shell")
            subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
                capture_output=True, timeout=3
            )
            return True, f"Громкость изменена"
        except Exception:
            pass
    return False, "Управление звуком не поддерживается"


def get_volume() -> Tuple[bool, int]:
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            return True, int(volume.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            pass
    return False, 0


def toggle_mute() -> Tuple[bool, str]:
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            is_muted = volume.GetMute()
            volume.SetMute(not is_muted, None)
            return True, "Звук выключен" if not is_muted else "Звук включён"
        except Exception as e:
            return False, str(e)
    return False, "Управление звуком не поддерживается"


def toggle_microphone() -> Tuple[bool, str]:
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                is_muted = volume.GetMute()
                volume.SetMute(not is_muted, None)
                return True, "Микрофон выключен" if not is_muted else "Микрофон включён"
        except Exception as e:
            logger.error(f"Ошибка микрофона: {e}")
    return True, "Переключил микрофон"


# ── Управление окнами ─────────────────────────────────────────────────────────

def minimize_all_windows() -> Tuple[bool, str]:
    """Свернуть все окна (Win+D аналог)."""
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "(New-Object -ComObject Shell.Application).MinimizeAll()"],
                capture_output=True, timeout=5
            )
            return True, "Свернул все окна, бро! Чисто."
        except Exception as e:
            logger.error(f"Ошибка сворачивания: {e}")
            # Fallback: Win+D через keyboard simulation
            try:
                import ctypes
                ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)   # Win down
                ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)   # D down
                ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)   # D up
                ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)   # Win up
                return True, "Свернул все окна!"
            except Exception:
                pass
    return False, "Сворачивание не поддерживается на этой ОС"


def restore_all_windows() -> Tuple[bool, str]:
    """Восстановить все свёрнутые окна."""
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "(New-Object -ComObject Shell.Application).UndoMinimizeALL()"],
                capture_output=True, timeout=5
            )
            return True, "Восстановил все окна, бро!"
        except Exception as e:
            return False, str(e)
    return False, "Не поддерживается"


# ── Браузер ──────────────────────────────────────────────────────────────────

def open_browser(url: str = "") -> Tuple[bool, str]:
    try:
        target = url if url else "https://www.google.com"
        webbrowser.open(target)
        return True, f"Открываю браузер{': ' + url if url else ''}"
    except Exception as e:
        return False, str(e)


def open_youtube(query: str = "") -> Tuple[bool, str]:
    if query:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    else:
        url = "https://www.youtube.com"
    return open_browser(url)


# ── Приложения и игры ─────────────────────────────────────────────────────────

# Steam App IDs для популярных игр
STEAM_GAME_IDS = {
    "rust":              252490,
    "раст":              252490,
    "cs2":               730,
    "cs 2":              730,
    "counter-strike 2":  730,
    "контр страйк":      730,
    "контрстрайк":       730,
    "csgo":              730,
    "cs:go":             730,
    "dota":              570,
    "dota 2":            570,
    "дота":              570,
    "pubg":              578080,
    "gta":               271590,
    "gta 5":             271590,
    "gta v":             271590,
    "cyberpunk":         1091500,
    "cyberpunk 2077":    1091500,
    "киберпанк":         1091500,
    "apex":              1172470,
    "apex legends":      1172470,
    "апекс":             1172470,
    "terraria":          105600,
    "террария":          105600,
    "stardew":           413150,
    "stardew valley":    413150,
    "among us":          945360,
    "амонг ас":          945360,
    "valheim":           892970,
    "валхейм":           892970,
    "the forest":        242760,
    "minecraft":         None,  # не в Steam
    "майнкрафт":         None,
}

# Пути к приложениям
APP_PATHS = {
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ],
    "discord": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "Update.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "Discord", "discord.exe"),
    ],
    "telegram": [
        os.path.join(os.environ.get("APPDATA", ""), "Telegram Desktop", "Telegram.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Telegram Desktop", "Telegram.exe"),
    ],
    "vscode": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "spotify": [
        os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "Spotify.exe"),
    ],
    "notepad":           ["notepad.exe"],
    "блокнот":           ["notepad.exe"],
    "проводник":         ["explorer.exe"],
    "explorer":          ["explorer.exe"],
    "калькулятор":       ["calc.exe"],
    "calculator":        ["calc.exe"],
    "calc":              ["calc.exe"],
    "paint":             ["mspaint.exe"],
    "диспетчер задач":   ["taskmgr.exe"],
    "taskmgr":           ["taskmgr.exe"],
    "cmd":               ["cmd.exe"],
    "powershell":        ["powershell.exe"],
    "word":              [r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"],
    "excel":             [r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"],
}


def _launch_steam_game(game_id: int) -> Tuple[bool, str]:
    """Запустить игру через Steam по App ID."""
    url = f"steam://rungameid/{game_id}"
    try:
        webbrowser.open(url)
        return True, f"Запускаю игру через Steam! Are you ready? Let's go!"
    except Exception as e:
        return False, f"Не удалось запустить Steam игру: {e}"


def open_application(app_name: str) -> Tuple[bool, str]:
    """Открыть приложение или игру."""
    name_lower = app_name.lower().strip()

    # 1. Проверяем Steam игры
    for game_key, game_id in STEAM_GAME_IDS.items():
        if game_key in name_lower or name_lower in game_key:
            if game_id is None:
                return False, f"Игра '{app_name}' не в Steam. Открой лаунчер вручную."
            return _launch_steam_game(game_id)

    # 2. Проверяем известные приложения
    for key, paths in APP_PATHS.items():
        if key in name_lower or name_lower in key:
            for path in paths:
                if os.path.isabs(path) and os.path.exists(path):
                    try:
                        if "Discord" in path and "Update.exe" in path:
                            subprocess.Popen([path, "--processStart", "Discord.exe"])
                        else:
                            subprocess.Popen([path])
                        return True, f"Открываю {app_name}!"
                    except Exception as e:
                        logger.error(f"Ошибка запуска {path}: {e}")
                else:
                    try:
                        subprocess.Popen(path, shell=True)
                        return True, f"Открываю {app_name}!"
                    except Exception:
                        pass

    # 3. Попытка запуска как есть
    try:
        subprocess.Popen(app_name, shell=True)
        return True, f"Пробую открыть {app_name}..."
    except Exception:
        return False, (f"Не нашёл '{app_name}', бро. "
                       f"Убедись что приложение установлено.")


def close_application(app_name: str) -> Tuple[bool, str]:
    if IS_WINDOWS:
        proc_map = {
            "браузер": ["chrome.exe", "firefox.exe", "msedge.exe"],
            "discord": ["discord.exe"],
            "steam":   ["steam.exe"],
            "spotify": ["Spotify.exe"],
            "telegram": ["Telegram.exe"],
        }
        processes = []
        for key, procs in proc_map.items():
            if key in app_name.lower():
                processes = procs
                break
        if not processes:
            processes = [f"{app_name}.exe", app_name]

        killed = False
        for proc in processes:
            try:
                r = subprocess.run(["taskkill", "/F", "/IM", proc],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    killed = True
            except Exception:
                pass
        if killed:
            return True, f"Закрыл {app_name}!"
        return False, f"Не нашёл процесс '{app_name}'"
    return False, "Не поддерживается"


# ── Системные операции ────────────────────────────────────────────────────────

def lock_screen() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Экран заблокирован. Wrestle with the best!"
        except Exception:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return True, "Экран заблокирован"
    return False, "Блокировка не поддерживается"


def sleep_computer() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 "Add-Type -Assembly System.Windows.Forms; "
                 "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"],
                timeout=5
            )
            return True, "Компьютер уходит в сон. Goodnight, bro!"
        except Exception as e:
            return False, str(e)
    return False, "Спящий режим не поддерживается"


def shutdown_computer(delay_sec: int = 30) -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/s", "/t", str(delay_sec)])
            return True, f"Выключение через {delay_sec} секунд. Bye-bye, bro!"
        except Exception as e:
            return False, str(e)
    return False, "Не поддерживается"


def restart_computer() -> Tuple[bool, str]:
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"])
            return True, "Перезагружаю! Are you ready?"
        except Exception as e:
            return False, str(e)
    return False, "Не поддерживается"


def take_screenshot() -> Tuple[bool, str]:
    try:
        import PIL.ImageGrab
        import time
        fn = f"screenshot_{int(time.time())}.png"
        dest = os.path.join(os.path.expanduser("~"), "Desktop", fn)
        PIL.ImageGrab.grab().save(dest)
        return True, f"Скриншот сохранён на рабочем столе: {fn}"
    except ImportError:
        if IS_WINDOWS:
            try:
                subprocess.run(["snippingtool"])
                return True, "Открыт инструмент снимка"
            except Exception:
                pass
        return False, "PIL не установлен"
    except Exception as e:
        return False, str(e)


def open_url(url: str) -> Tuple[bool, str]:
    if not url.startswith("http"):
        url = "https://" + url
    return open_browser(url)


# ── Генерация промпта (специальный маркер для UI) ─────────────────────────────

PROMPT_MARKER = "__PROMPT_RESULT__:"


def mark_as_prompt(prompt_text: str) -> str:
    """Обернуть текст промпта в маркер, чтобы UI показал кнопку копирования."""
    return f"{PROMPT_MARKER}{prompt_text}"


def is_prompt_result(text: str) -> bool:
    return text.startswith(PROMPT_MARKER)


def extract_prompt(text: str) -> str:
    return text[len(PROMPT_MARKER):]


# ── Словарь приложений для парсера ────────────────────────────────────────────

_OPEN_APP_RE = re.compile(
    r"(?:открой|запусти|включи|запусти мне|открой мне)\s+(.+)",
    re.IGNORECASE,
)
_CLOSE_APP_RE = re.compile(
    r"(?:закрой|вырубай|убей)\s+(.+)",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(
    r"(?:громкость|звук)\s+(\d+)\s*%?",
    re.IGNORECASE,
)
_VOLUME_SET_RE = re.compile(
    r"(?:сделай|поставь|установи)\s+(?:звук|громкость)\s+(?:на\s+)?(\d+)\s*%?",
    re.IGNORECASE,
)
_YT_SEARCH_RE = re.compile(
    r"(?:найди|открой|включи)\s+(?:на\s+)?youtube\s+(.+)|"
    r"youtube\s+(.+)",
    re.IGNORECASE,
)
_MINIMIZE_RE = re.compile(
    r"(?:сверни|скрой|спрячь)\s+(?:все\s+)?(?:окна|вкладки|приложения)",
    re.IGNORECASE,
)
_RESTORE_RE = re.compile(
    r"(?:разверни|восстанови)\s+(?:все\s+)?(?:окна|вкладки)",
    re.IGNORECASE,
)


COMMAND_PATTERNS = [
    (_MINIMIZE_RE,   lambda m: minimize_all_windows()),
    (_RESTORE_RE,    lambda m: restore_all_windows()),
    (_VOLUME_SET_RE, lambda m: set_volume(int(m.group(1)))),
    (_VOLUME_RE,     lambda m: set_volume(int(m.group(1)))),
    (re.compile(r"(?:отключи|выключи)\s+(?:звук|аудио)", re.I),
                     lambda m: toggle_mute()),
    (re.compile(r"(?:включи|переключи)\s+(?:микрофон|мик)", re.I),
                     lambda m: toggle_microphone()),
    (_YT_SEARCH_RE,  lambda m: open_youtube(m.group(1) or m.group(2) or "")),
    (re.compile(r"(?:открой|запусти)\s+(?:youtube|ютуб)$", re.I),
                     lambda m: open_youtube()),
    (re.compile(r"(?:открой|запусти)\s+(?:браузер|хром|firefox|edge|opera)", re.I),
                     lambda m: open_browser()),
    (_OPEN_APP_RE,   lambda m: open_application(m.group(1).strip())),
    (_CLOSE_APP_RE,  lambda m: close_application(m.group(1).strip())),
    (re.compile(r"(?:заблокируй|заблокировать)\s+(?:экран|компьютер)", re.I),
                     lambda m: lock_screen()),
    (re.compile(r"(?:выключи|shutdown)\s+(?:компьютер|пк|комп)", re.I),
                     lambda m: shutdown_computer(30)),
    (re.compile(r"(?:перезагрузи|restart)\s+(?:компьютер|пк|комп)", re.I),
                     lambda m: restart_computer()),
    (re.compile(r"скриншот|снимок экрана", re.I),
                     lambda m: take_screenshot()),
    (re.compile(r"спящий режим|усыпи компьютер", re.I),
                     lambda m: sleep_computer()),
]


def try_parse_command(text: str) -> Optional[Tuple[bool, str]]:
    """
    Распознать системную команду из текста.
    Возвращает (success, message) или None если команда не распознана.
    """
    text_lower = text.lower().strip()

    for pattern, handler in COMMAND_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            try:
                return handler(match)
            except Exception as e:
                logger.error(f"Ошибка команды: {e}")
                return False, str(e)

    return None
