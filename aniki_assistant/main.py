"""
Аники — ИИ-ассистент Билли Херрингтон
Главная точка входа
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
            encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger("aniki.main")

os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

def check_dependencies() -> list[str]:
    """Проверить наличие зависимостей."""
    missing = []
    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")
    try:
        import requests
    except ImportError:
        missing.append("requests")
    return missing


def show_dependency_error(missing: list[str]):
    """Показать ошибку зависимостей."""
    print(f"ОШИБКА: Не установлены пакеты: {', '.join(missing)}")
    print("Запусти: pip install " + " ".join(missing))

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Аники — Ошибка запуска",
            f"Не установлены пакеты:\n{chr(10).join(missing)}\n\n"
            f"Запусти setup.bat для установки зависимостей!"
        )
    except Exception:
        pass


def main():
    """Точка входа приложения."""
    missing = check_dependencies()
    if missing:
        show_dependency_error(missing)
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QColor

    app = QApplication(sys.argv)
    app.setApplicationName("Аники")
    app.setApplicationVersion("1.0.0")

    splash_pixmap = QPixmap(400, 200)
    splash_pixmap.fill(QColor("#1a1a2e"))
    splash = QSplashScreen(splash_pixmap)
    splash_label = QLabel(splash)
    splash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    splash_label.setGeometry(0, 0, 400, 200)
    splash_label.setStyleSheet("color: #ff9e44; font-size: 28px; font-weight: bold;")
    splash_label.setText("🤜 Аники загружается...\nAre you ready?")
    splash.show()
    app.processEvents()

    logger.info("Инициализация Аники...")

    splash.showMessage("Инициализация памяти...", alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, color=QColor("#888"))
    app.processEvents()

    from core.memory import init_db
    init_db()
    logger.info("База данных инициализирована")

    splash.showMessage("Проверка Ollama...", alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, color=QColor("#888"))
    app.processEvents()

    from core.ai_engine import AnikiAI, check_ollama_available
    ai_engine = AnikiAI()
    ollama_ok = check_ollama_available()

    if not ollama_ok:
        logger.warning("Ollama не запущен — ИИ-функции недоступны")

    splash.showMessage("Загрузка TTS...", alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, color=QColor("#888"))
    app.processEvents()

    from core.tts import preload as tts_preload
    tts_thread = threading.Thread(target=tts_preload, daemon=True)
    tts_thread.start()

    splash.showMessage("Запуск интерфейса...", alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, color=QColor("#888"))
    app.processEvents()

    from ui.chat_window import ChatWindow
    from core.reminders import ReminderSystem

    def on_reminder(title: str, message: str):
        """Callback для напоминаний."""
        if chat_window:
            chat_window.show_reminder_notification(title, message)
        from ui.tray import TrayApp
        if tray_app and tray_app.tray_icon:
            tray_app.show_notification(f"⏰ {title}", message)

    reminder_system = ReminderSystem(on_reminder=on_reminder)
    reminder_system.start()

    if ollama_ok:
        init_thread = threading.Thread(target=ai_engine.initialize, daemon=True)
        init_thread.start()

    chat_window = ChatWindow(
        ai_engine=ai_engine if ollama_ok else None,
        reminder_system=reminder_system,
        tts_enabled=True,
        stt_enabled=False,
    )

    from ui.tray import TrayApp
    tray_app = TrayApp(chat_window=chat_window)

    from PyQt6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("Системный трей недоступен")

    app.setQuitOnLastWindowClosed(False)

    def on_close_to_tray():
        """Скрыть окно в трей при закрытии."""
        chat_window.hide()
        tray_app.show_notification(
            "Аники",
            "Я в трее! Are you ready? Кликни на иконку чтобы открыть меня."
        )

    original_close = chat_window.closeEvent

    def close_event(event):
        event.ignore()
        on_close_to_tray()

    chat_window.closeEvent = close_event

    QTimer.singleShot(1500, splash.close)

    if not ollama_ok:
        QTimer.singleShot(2000, lambda: chat_window.add_bot_message(
            "⚠️ Бро, Ollama не запущен!\n\n"
            "Для работы ИИ:\n"
            "1. Установи Ollama: https://ollama.com\n"
            "2. Открой cmd и запусти: ollama run mistral\n"
            "3. Перезапусти Аники\n\n"
            "Let's go — всё будет работать!"
        ))

    logger.info("Аники запущен!")
    sys.exit(tray_app.run())


if __name__ == "__main__":
    main()
