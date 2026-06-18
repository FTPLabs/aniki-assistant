"""
Обработчик системных команд Windows.
Управляет браузером, звуком, микрофоном, приложениями и т.д.
"""

import subprocess
import os
import sys
import re
import webbrowser
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Определяем тип ОС
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


def set_volume(percent: int) -> Tuple[bool, str]:
    """Установить громкость системы (0-100%)."""
    percent = max(0, min(100, percent))
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            scalar = percent / 100.0
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return True, f"Громкость установлена на {percent}%"
        except Exception as e:
            logger.error(f"Ошибка установки громкости: {e}")
            return False, f"Не удалось установить громкость: {e}"
    elif IS_WINDOWS:
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"$vol = {percent}/100; (New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
                capture_output=True
            )
            return True, f"Громкость примерно {percent}%"
        except Exception as e:
            return False, str(e)
    return False, "Управление звуком не поддерживается на этой ОС"


def get_volume() -> Tuple[bool, int]:
    """Получить текущую громкость."""
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            scalar = volume.GetMasterVolumeLevelScalar()
            return True, int(scalar * 100)
        except Exception as e:
            return False, 0
    return False, 0


def toggle_mute() -> Tuple[bool, str]:
    """Переключить состояние отключения звука."""
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            is_muted = volume.GetMute()
            volume.SetMute(not is_muted, None)
            state = "отключён" if not is_muted else "включён"
            return True, f"Звук {state}"
        except Exception as e:
            return False, str(e)
    return False, "Управление звуком не поддерживается"


def toggle_microphone() -> Tuple[bool, str]:
    """Включить/отключить микрофон."""
    if IS_WINDOWS and PYCAW_AVAILABLE:
        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                is_muted = volume.GetMute()
                volume.SetMute(not is_muted, None)
                state = "отключён" if not is_muted else "включён"
                return True, f"Микрофон {state}"
        except Exception as e:
            logger.error(f"Ошибка переключения микрофона: {e}")
    if IS_WINDOWS:
        try:
            ps_cmd = """
            $mic = Get-WmiObject -Class Win32_SoundDevice | Where-Object {$_.Name -like '*microphone*' -or $_.Name -like '*микрофон*'}
            if ($mic) { "found" } else { "notfound" }
            """
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            return True, "Переключил микрофон"
        except Exception as e:
            return False, str(e)
    return False, "Управление микрофоном не поддерживается"


def open_browser(url: str = "") -> Tuple[bool, str]:
    """Открыть браузер."""
    try:
        if url:
            webbrowser.open(url)
            return True, f"Открываю {url}"
        else:
            webbrowser.open("https://www.google.com")
            return True, "Открываю браузер"
    except Exception as e:
        return False, str(e)


def open_youtube(query: str = "") -> Tuple[bool, str]:
    """Открыть YouTube."""
    if query:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    else:
        url = "https://www.youtube.com"
    return open_browser(url)


def open_application(app_name: str) -> Tuple[bool, str]:
    """Открыть приложение по имени."""
    app_name_lower = app_name.lower()

    app_map = {
        "steam": ["C:\\Program Files (x86)\\Steam\\steam.exe",
                  "C:\\Program Files\\Steam\\steam.exe"],
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
            "C:\\Program Files\\Microsoft VS Code\\Code.exe",
        ],
        "spotify": [
            os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Spotify", "Spotify.exe"),
        ],
        "notepad": ["notepad.exe"],
        "проводник": ["explorer.exe"],
        "explorer": ["explorer.exe"],
        "калькулятор": ["calc.exe"],
        "calculator": ["calc.exe"],
        "paint": ["mspaint.exe"],
        "taskmanager": ["taskmgr.exe"],
        "диспетчер задач": ["taskmgr.exe"],
        "cmd": ["cmd.exe"],
        "powershell": ["powershell.exe"],
    }

    paths = None
    for key, app_paths in app_map.items():
        if key in app_name_lower or app_name_lower in key:
            paths = app_paths
            break

    if paths:
        for path in paths:
            if os.path.exists(path):
                try:
                    subprocess.Popen([path])
                    return True, f"Открываю {app_name}"
                except Exception as e:
                    logger.error(f"Ошибка открытия {path}: {e}")
            else:
                try:
                    subprocess.Popen(path, shell=True)
                    return True, f"Открываю {app_name}"
                except Exception:
                    pass

    try:
        subprocess.Popen(app_name, shell=True)
        return True, f"Пробую открыть {app_name}"
    except Exception as e:
        return False, f"Не нашёл приложение '{app_name}'"


def close_application(app_name: str) -> Tuple[bool, str]:
    """Закрыть приложение."""
    if IS_WINDOWS:
        process_map = {
            "браузер": ["chrome.exe", "firefox.exe", "msedge.exe", "opera.exe"],
            "discord": ["discord.exe"],
            "steam": ["steam.exe"],
            "spotify": ["Spotify.exe"],
            "telegram": ["Telegram.exe"],
        }

        processes = []
        for key, procs in process_map.items():
            if key in app_name.lower():
                processes = procs
                break

        if not processes:
            processes = [f"{app_name}.exe", app_name]

        killed = False
        for proc in processes:
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    killed = True
            except Exception:
                pass

        if killed:
            return True, f"Закрыл {app_name}"
        return False, f"Не нашёл процесс '{app_name}'"
    return False, "Закрытие приложений не поддерживается"


def lock_screen() -> Tuple[bool, str]:
    """Заблокировать экран."""
    if IS_WINDOWS:
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Экран заблокирован"
        except Exception:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return True, "Экран заблокирован"
    return False, "Блокировка не поддерживается"


def sleep_computer() -> Tuple[bool, str]:
    """Перевести компьютер в спящий режим."""
    if IS_WINDOWS:
        try:
            subprocess.run(["powershell", "-Command", "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])
            return True, "Компьютер уходит в сон"
        except Exception as e:
            return False, str(e)
    return False, "Спящий режим не поддерживается"


def shutdown_computer(delay_sec: int = 0) -> Tuple[bool, str]:
    """Выключить компьютер."""
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/s", "/t", str(delay_sec)])
            return True, f"Выключение через {delay_sec} секунд"
        except Exception as e:
            return False, str(e)
    return False, "Выключение не поддерживается"


def restart_computer() -> Tuple[bool, str]:
    """Перезагрузить компьютер."""
    if IS_WINDOWS:
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"])
            return True, "Перезагружаю компьютер"
        except Exception as e:
            return False, str(e)
    return False, "Перезагрузка не поддерживается"


def take_screenshot() -> Tuple[bool, str]:
    """Сделать скриншот."""
    try:
        import PIL.ImageGrab
        import time
        filename = f"screenshot_{int(time.time())}.png"
        desktop = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        img = PIL.ImageGrab.grab()
        img.save(desktop)
        return True, f"Скриншот сохранён на рабочий стол: {filename}"
    except ImportError:
        if IS_WINDOWS:
            try:
                subprocess.run(["snippingtool"])
                return True, "Открыт инструмент снимка экрана"
            except Exception:
                pass
        return False, "PIL не установлен для скриншотов"
    except Exception as e:
        return False, str(e)


def open_url(url: str) -> Tuple[bool, str]:
    """Открыть URL в браузере."""
    if not url.startswith("http"):
        url = "https://" + url
    return open_browser(url)


COMMAND_PATTERNS = [
    (r"(открой|запусти|включи)\s+(браузер|хром|хромиум|firefox|edge|opera)", lambda m: open_browser()),
    (r"(открой|запусти)\s+youtube|ютуб", lambda m: open_youtube()),
    (r"(открой|запусти)\s+(discord|дискорд)", lambda m: open_application("discord")),
    (r"(открой|запусти)\s+(steam|стим)", lambda m: open_application("steam")),
    (r"(открой|запусти)\s+(spotify|спотифай)", lambda m: open_application("spotify")),
    (r"(открой|запусти)\s+(telegram|телеграм)", lambda m: open_application("telegram")),
    (r"громкость\s+(\d+)\s*%?", lambda m: set_volume(int(m.group(1)))),
    (r"(сделай|поставь|установи)\s+звук\s+(\d+)\s*%?", lambda m: set_volume(int(m.group(2)))),
    (r"(звук|громкость)\s+(\d+)\s*%?", lambda m: set_volume(int(m.group(2)))),
    (r"(отключи|выключи)\s+(звук|аудио)", lambda m: toggle_mute()),
    (r"(включи|отключи|переключи)\s+(микрофон|мик)", lambda m: toggle_microphone()),
    (r"(заблокируй|заблокировать)\s+(экран|компьютер)", lambda m: lock_screen()),
    (r"(выключи|shutdown)\s+(компьютер|пк|комп)", lambda m: shutdown_computer(30)),
    (r"(перезагрузи|restart)\s+(компьютер|пк|комп)", lambda m: restart_computer()),
    (r"(скриншот|снимок экрана)", lambda m: take_screenshot()),
]


def try_parse_command(text: str) -> Optional[Tuple[bool, str]]:
    """
    Попытаться распознать команду из текста.
    Возвращает (success, message) или None если команда не распознана.
    """
    text_lower = text.lower().strip()

    for pattern, handler in COMMAND_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            try:
                result = handler(match)
                return result
            except Exception as e:
                logger.error(f"Ошибка выполнения команды '{pattern}': {e}")
                return False, str(e)

    return None
