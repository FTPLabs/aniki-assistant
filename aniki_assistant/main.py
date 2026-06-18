"""
Аники — ИИ-ассистент Билли Херрингтона
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
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("aniki.main")

os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)


def check_dependencies() -> list[str]:
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
            "Запусти setup.bat для установки зависимостей!",
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
    app.setApplicationVersion("2.0.0")

    # Сплэш экран
    splash_pixmap = QPixmap(420, 220)
    splash_pixmap.fill(QColor("#0d0d1e"))
    splash = QSplashScreen(splash_pixmap)
    lbl = QLabel(splash)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setGeometry(0, 0, 420, 220)
    lbl.setStyleSheet(
        "color: #ff9e44; font-size: 26px; font-weight: bold; font-family: 'Segoe UI';"
    )
    lbl.setText("АНИКИ\nAre you ready?\nЗагружаюсь...")
    splash.show()
    app.processEvents()

    logger.info("Инициализация Аники v2.0...")

    # База данных
    splash.showMessage(
        "Инициализация памяти...",
        alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        color=QColor("#888"),
    )
    app.processEvents()
    from core.memory import init_db
    init_db()

    # Проверка Ollama
    splash.showMessage(
        "Проверка Ollama...",
        alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        color=QColor("#888"),
    )
    app.processEvents()
    from core.ai_engine import AnikiAI, check_ollama_available
    ai_engine = AnikiAI()
    ollama_ok = check_ollama_available()
    if not ollama_ok:
        logger.warning("Ollama не запущен — ИИ-функции недоступны")

    # TTS предзагрузка
    splash.showMessage(
        "Загрузка голоса (Silero)...",
        alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        color=QColor("#888"),
    )
    app.processEvents()
    from core.tts import preload as tts_preload
    threading.Thread(target=tts_preload, daemon=True).start()

    # Интерфейс
    splash.showMessage(
        "Запуск интерфейса...",
        alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        color=QColor("#888"),
    )
    app.processEvents()

    from ui.chat_window import ChatWindow
    from core.reminders import ReminderSystem

    tray_app = None
    chat_window = None

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
        stt_enabled=False,
    )

    # Аватар — плавающее окно поверх всего
    avatar_overlay = None
    try:
        from ui.avatar_overlay import AvatarOverlay
        avatar_overlay = AvatarOverlay()
        avatar_overlay.show()

        # Подключаем сигналы чата к аватару
        chat_window.avatar_thinking.connect(avatar_overlay.set_thinking)
        chat_window.avatar_speaking.connect(avatar_overlay.set_speaking)

        # Клик на аватар — показать/скрыть чат
        def _toggle_chat():
            if chat_window.isVisible():
                chat_window.hide()
            else:
                chat_window.show()
                chat_window.raise_()
                chat_window.activateWindow()

        avatar_overlay.toggle_main.connect(_toggle_chat)
        logger.info("Аватар-оверлей запущен")
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
                "Я в трее! Кликни на иконку или на аватар чтобы открыть меня. Are you ready?",
            )

    chat_window.closeEvent = close_to_tray

    QTimer.singleShot(1600, splash.close)

    if not ollama_ok:
        QTimer.singleShot(2000, lambda: chat_window.add_bot_message(
            "Бро, Ollama не запущен!\n\n"
            "Для полноценного ИИ:\n"
            "1. Установи Ollama: https://ollama.com\n"
            "2. Открой cmd: ollama run mistral\n"
            "3. Перезапусти Аники\n\n"
            "Let's go — всё будет работать!"
        ))

    logger.info("Аники v2.0 запущен! Are you ready?")
    sys.exit(tray_app.run())


if __name__ == "__main__":
    main()
