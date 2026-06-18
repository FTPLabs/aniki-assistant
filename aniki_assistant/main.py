"""
Аники v2.1 — ИИ-ассистент Билли Херрингтона
Точка входа: VAD, аватар, чат, трей, напоминания.
"""

import sys
import os
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "data", "aniki.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("aniki.main")
os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)


def check_dependencies() -> list:
    missing = []
    for pkg in ("PyQt6", "requests"):
        try:
            __import__(pkg.replace("-", "_").split(">=")[0])
        except ImportError:
            missing.append(pkg)
    return missing


def show_dependency_error(missing: list):
    print(f"ОШИБКА: не установлены пакеты: {', '.join(missing)}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(
            "Аники — Ошибка",
            f"Не установлены:\n{chr(10).join(missing)}\n\n"
            "Запусти setup.bat для установки.",
        )
    except Exception:
        pass


def main():
    missing = check_dependencies()
    if missing:
        show_dependency_error(missing)
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QColor

    app = QApplication(sys.argv)
    app.setApplicationName("Аники")
    app.setApplicationVersion("2.1.0")

    # Сплэш
    pix = QPixmap(440, 230)
    pix.fill(QColor("#0d0d1e"))
    splash = QSplashScreen(pix)
    lbl = QLabel(splash)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setGeometry(0, 0, 440, 230)
    lbl.setStyleSheet(
        "color:#ff9e44; font-size:24px; font-weight:bold; font-family:'Segoe UI';"
    )
    lbl.setText("АНИКИ\nAre you ready?\nЗагружаюсь...")
    splash.show()
    app.processEvents()

    def splash_msg(msg: str):
        splash.showMessage(
            msg,
            alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            color=QColor("#888"),
        )
        app.processEvents()

    logger.info("Аники v2.1 запускается...")

    # База данных
    splash_msg("Инициализация памяти...")
    from core.memory import init_db
    init_db()

    # Ollama
    splash_msg("Проверка Ollama...")
    from core.ai_engine import AnikiAI, check_ollama_available
    ai_engine = AnikiAI()
    ollama_ok = check_ollama_available()
    if not ollama_ok:
        logger.warning("Ollama не запущен — ИИ недоступен")

    # TTS предзагрузка
    splash_msg("Загрузка голоса Silero (aidar)...")
    from core.tts import preload as tts_preload
    threading.Thread(target=tts_preload, daemon=True).start()

    # STT предзагрузка (Whisper)
    splash_msg("Загрузка Whisper STT...")
    from core.speech import load_whisper_model, is_available as stt_ok
    stt_available = stt_ok()
    if stt_available:
        threading.Thread(target=load_whisper_model, daemon=True).start()
    else:
        logger.warning("STT (faster-whisper) недоступен — VAD отключён")

    # Интерфейс
    splash_msg("Запуск интерфейса...")
    from ui.chat_window import ChatWindow
    from core.reminders import ReminderSystem

    chat_window  = None
    tray_app     = None
    avatar_overlay = None

    def on_reminder(title: str, message: str):
        if chat_window:
            chat_window.show_reminder_notification(title, message)
        if tray_app and tray_app.tray_icon:
            tray_app.show_notification(f"⏰ {title}", message)

    reminder_system = ReminderSystem(on_reminder=on_reminder)
    reminder_system.start()

    if ollama_ok:
        threading.Thread(target=ai_engine.initialize, daemon=True).start()

    chat_window = ChatWindow(
        ai_engine=ai_engine if ollama_ok else None,
        reminder_system=reminder_system,
        tts_enabled=True,
        stt_enabled=stt_available,
    )

    # Аватар Билли Херрингтона
    splash_msg("Запуск аватара...")
    try:
        from ui.avatar_overlay import AvatarOverlay
        avatar_overlay = AvatarOverlay()
        avatar_overlay.show()

        chat_window.avatar_thinking.connect(avatar_overlay.set_thinking)
        chat_window.avatar_speaking.connect(avatar_overlay.set_speaking)
        chat_window.avatar_listening.connect(avatar_overlay.set_listening)

        def _toggle_chat():
            if chat_window.isVisible():
                chat_window.hide()
            else:
                chat_window.show()
                chat_window.raise_()
                chat_window.activateWindow()

        avatar_overlay.toggle_main.connect(_toggle_chat)
        logger.info("Аватар Билли запущен")
    except Exception as e:
        logger.warning(f"Аватар недоступен: {e}")

    # Трей
    from ui.tray import TrayApp
    tray_app = TrayApp(chat_window=chat_window)

    from PyQt6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("Системный трей недоступен")

    app.setQuitOnLastWindowClosed(False)

    def close_to_tray(event):
        event.ignore()
        chat_window.hide()
        if tray_app:
            tray_app.show_notification(
                "Аники",
                "Я в трее! Кликни на аватар Билли или иконку в трее.",
            )

    chat_window.closeEvent = close_to_tray

    QTimer.singleShot(1800, splash.close)

    if not ollama_ok:
        QTimer.singleShot(2200, lambda: chat_window.add_bot_message(
            "Бро, Ollama не запущен!\n\n"
            "Для работы ИИ:\n"
            "1. Установи Ollama: https://ollama.com\n"
            "2. В cmd: ollama run mistral\n"
            "3. Перезапусти Аники\n\n"
            "Let's go — всё будет работать!"
        ))

    if not stt_available:
        QTimer.singleShot(2500, lambda: chat_window.add_bot_message(
            "VAD недоступен (faster-whisper не установлен).\n"
            "Голосовое управление отключено — пиши текстом."
        ))

    logger.info("Аники v2.1 запущен! Are you ready?")
    sys.exit(tray_app.run())


if __name__ == "__main__":
    main()
