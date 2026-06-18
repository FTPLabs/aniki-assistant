"""
Системный трей Аники — PyQt6.
"""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import (
        QApplication, QSystemTrayIcon, QMenu, QWidget
    )
    from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
    from PyQt6.QtCore import Qt, QSize
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


def _create_default_icon() -> "QIcon":
    """Создать иконку трея по умолчанию (если нет файла)."""
    from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor("#1a1a2e"))
    painter.setPen(QColor("#ff9e44"))
    painter.drawEllipse(2, 2, 60, 60)

    font = QFont("Arial", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ff9e44"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    painter.end()

    return QIcon(pixmap)


def get_icon_path() -> str:
    """Получить путь к иконке."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    icon_path = os.path.join(base_dir, "resources", "aniki.ico")
    if os.path.exists(icon_path):
        return icon_path
    png_path = os.path.join(base_dir, "resources", "aniki.png")
    if os.path.exists(png_path):
        return png_path
    return ""


if PYQT_AVAILABLE:
    class TrayApp:
        """Приложение в системном трее."""

        def __init__(self, chat_window=None):
            self.app = QApplication.instance() or QApplication(sys.argv)
            self.chat_window = chat_window
            self.tray_icon: Optional[QSystemTrayIcon] = None
            self._setup_tray()

        def _setup_tray(self):
            icon_path = get_icon_path()
            if icon_path:
                icon = QIcon(icon_path)
            else:
                icon = _create_default_icon()

            self.tray_icon = QSystemTrayIcon(icon, self.app)
            self.tray_icon.setToolTip("🤜 Аники — ИИ-ассистент")

            menu = QMenu()
            menu.setStyleSheet("""
                QMenu {
                    background-color: #1a1a2e;
                    color: white;
                    border: 1px solid #2a2a4e;
                    border-radius: 8px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 8px 20px;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #2a2a4e;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #2a2a4e;
                    margin: 4px;
                }
            """)

            show_action = menu.addAction("🤜 Открыть Аники")
            show_action.triggered.connect(self.show_window)

            menu.addSeparator()

            mute_action = menu.addAction("🔇 Заглушить микрофон")
            mute_action.triggered.connect(self._toggle_mic)

            volume_30 = menu.addAction("🔉 Громкость 30%")
            volume_30.triggered.connect(lambda: self._set_vol(30))

            volume_50 = menu.addAction("🔊 Громкость 50%")
            volume_50.triggered.connect(lambda: self._set_vol(50))

            volume_100 = menu.addAction("🔊 Громкость 100%")
            volume_100.triggered.connect(lambda: self._set_vol(100))

            menu.addSeparator()

            quit_action = menu.addAction("✕ Выход")
            quit_action.triggered.connect(self.quit)

            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            self.tray_icon.show()

        def _on_tray_activated(self, reason):
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.show_window()

        def show_window(self):
            if self.chat_window:
                self.chat_window.show()
                self.chat_window.raise_()
                self.chat_window.activateWindow()

        def hide_window(self):
            if self.chat_window:
                self.chat_window.hide()

        def show_notification(self, title: str, message: str, duration_ms: int = 5000):
            """Показать системное уведомление."""
            if self.tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
                self.tray_icon.showMessage(
                    title,
                    message,
                    QSystemTrayIcon.MessageIcon.Information,
                    duration_ms
                )

        def _toggle_mic(self):
            from core.commands import toggle_microphone
            toggle_microphone()

        def _set_vol(self, percent: int):
            from core.commands import set_volume
            set_volume(percent)

        def quit(self):
            if self.tray_icon:
                self.tray_icon.hide()
            self.app.quit()

        def run(self):
            """Запустить цикл событий."""
            if self.chat_window:
                self.chat_window.show()
            return self.app.exec()
