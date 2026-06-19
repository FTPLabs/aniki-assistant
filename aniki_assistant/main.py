"""
Аники v3.0 — точка входа. Are you ready?
"""

import sys
import os
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "data", "aniki.log"),
            encoding="utf-8",
            delay=True,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("aniki.main")
os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)


def main():
    # ── Шаг 1: авто-установка зависимостей ───────────────────────────────────
    if not getattr(sys, "frozen", False):
        try:
            import auto_setup
            auto_setup.run(progress_cb=lambda msg: print(f"  {msg}"))
            auto_setup.ensure_ollama_autostart()
            auto_setup.download_billy_voice(background=True)
        except Exception as e:
            print(f"auto_setup: {e}")
    else:
        try:
            import auto_setup
            auto_setup.ensure_ollama_autostart()
            auto_setup.download_billy_voice(background=True)
        except Exception as e:
            logger.debug(f"auto_setup (frozen): {e}")

    # ── Шаг 2: проверить PyQt6 ────────────────────────────────────────────────
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("ОШИБКА: PyQt6 не установлен. Запусти setup.bat.")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Аники", "PyQt6 не установлен.\nЗапусти setup.bat.")
        except Exception:
            pass
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QColor

    app = QApplication(sys.argv)
    app.setApplicationName("Аники")
    app.setApplicationVersion("3.0.0")

    # Сплэш
    pix = QPixmap(440, 230)
    pix.fill(QColor("#0d0d1e"))
    splash = QSplashScreen(pix)
    lbl = QLabel(splash)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setGeometry(0, 0, 440, 230)
    lbl.setStyleSheet("color:#ff9e44;font-size:24px;font-weight:bold;font-family:'Segoe UI';")
    lbl.setText("АНИКИ v3.0\nAre you ready?\nЗагружаюсь...")
    splash.show()
    app.processEvents()

    def splash_msg(msg: str):
        splash.showMessage(
            msg,
            alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            color=QColor("#888"),
        )
        app.processEvents()

    logger.info("Аники v3.0 запускается... Let's go!")

    splash_msg("Инициализация памяти...")
    from core.memory import init_db
    init_db()

    splash_msg("Проверка Ollama...")
    from core.ai_engine import AnikiAI, check_ollama_available
    ai_engine = AnikiAI()
    ollama_ok = check_ollama_available()
    if not ollama_ok:
        try:
            from ollama_setup import start_ollama
            splash_msg("Запускаю Ollama...")
            ollama_ok = start_ollama()
        except Exception:
            pass
    if not ollama_ok:
        logger.warning("Ollama не запущен — ИИ недоступен")

    splash_msg("Загрузка голоса Билли...")
    from core.tts import preload as tts_preload
    threading.Thread(target=tts_preload, daemon=True).start()

    splash_msg("Проверка микрофона...")
    from core.speech import load_whisper_model, is_available as stt_ok
    stt_available = stt_ok()
    if stt_available:
        threading.Thread(target=load_whisper_model, daemon=True).start()
    else:
        logger.warning("STT недоступен — только текстовый режим")

    splash_msg("Запуск интерфейса...")
    from ui.chat_window import ChatWindow
    from core.reminders import ReminderSystem

    def on_reminder(title: str, message: str):
        if chat_window:
            chat_window.show_reminder_notification(title, message)
        if tray_app and tray_app.tray_icon:
            tray_app.show_notification(f"Аники: {title}", message)

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

    splash_msg("Запуск аватара Билли...")
    avatar_overlay = None
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
    except Exception as e:
        logger.warning(f"Аватар недоступен: {e}")

    from ui.tray import TrayApp
    tray_app = TrayApp(chat_window=chat_window)

    app.setQuitOnLastWindowClosed(False)

    def closeEvent(event):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            chat_window,
            "Аники",
            "Свернуть в трей или выйти?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.ignore()
            chat_window.hide()
            tray_app.show_notification("Аники", "Я в трее! Кликни на аватар Билли.")
        elif reply == QMessageBox.StandardButton.No:
            event.accept()
            if avatar_overlay:
                avatar_overlay.close()
            tray_app.quit()
        else:
            event.ignore()

    chat_window.closeEvent = closeEvent

    QTimer.singleShot(1800, splash.close)

    # ── Приветственные сообщения — живые, не роботские ───────────────────────
    if not ollama_ok:
        QTimer.singleShot(2200, lambda: chat_window.add_bot_message(
            "Бро, запусти Ollama — без него я как без мозга!\n\n"
            "1. Скачай: https://ollama.com\n"
            "2. В терминале: ollama run mistral\n"
            "3. Перезапусти меня\n\nLet's go — всё будет работать!"
        ))

    if not stt_available:
        QTimer.singleShot(2500, lambda: chat_window.add_bot_message(
            "Микрофон недоступен — пиши мне текстом, бро!\n"
            "Работаю в текстовом режиме. Are you ready?"
        ))

    logger.info("Аники v3.0 запущен! Are you ready?")
    sys.exit(tray_app.run())


if __name__ == "__main__":
    main()
