"""
Аватар Билли Херрингтона v2.2 — реальное фото + анимация состояний.
FIX [C4]: QPainterPath импортируется статически вверху файла, а не через
          __import__() внутри paintEvent (вызывался 20 раз/сек).
"""

import logging
import os
import threading
import urllib.request

logger = logging.getLogger(__name__)

PHOTO_URL  = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Billy_Herrington_2018.jpg/220px-Billy_Herrington_2018.jpg"
PHOTO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "billy.jpg"
)

AVATAR_SIZE   = 120
BORDER_WIDTH  = 4

try:
    from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout
    from PyQt6.QtCore    import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal
    from PyQt6.QtGui     import (QPainter, QColor, QPixmap, QBrush,
                                  QPen, QFont, QMouseEvent, QImage,
                                  QPainterPath)   # FIX [C4]: статический импорт
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


def _download_photo():
    """Скачать фото Билли Херрингтона при первом запуске."""
    os.makedirs(os.path.dirname(PHOTO_PATH), exist_ok=True)
    if os.path.exists(PHOTO_PATH):
        return True
    try:
        req = urllib.request.Request(
            PHOTO_URL,
            headers={"User-Agent": "Mozilla/5.0 AnikiBuddy/2.2"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(PHOTO_PATH, "wb") as f:
                f.write(resp.read())
        logger.info("Фото Билли скачано")
        return True
    except Exception as e:
        logger.warning(f"Не удалось скачать фото Билли: {e}")
        return False


class AvatarState:
    IDLE      = "idle"
    THINKING  = "thinking"
    SPEAKING  = "speaking"
    LISTENING = "listening"

STATE_COLORS = {
    AvatarState.IDLE:      "#ff9e44",
    AvatarState.THINKING:  "#7755ff",
    AvatarState.SPEAKING:  "#44ccff",
    AvatarState.LISTENING: "#44ff88",
}

STATE_LABELS = {
    AvatarState.IDLE:      "Аники",
    AvatarState.THINKING:  "Думаю...",
    AvatarState.SPEAKING:  "Говорю!",
    AvatarState.LISTENING: "Слушаю...",
}


if PYQT_AVAILABLE:

    class BillyAvatar(QWidget):
        """Виджет аватара — круглое фото Билли с анимированной рамкой."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._state       = AvatarState.IDLE
            self._pixmap = None
            self._pulse       = 0.0
            self._pulse_dir   = 1
            self._border_color = QColor(STATE_COLORS[AvatarState.IDLE])

            self.setFixedSize(AVATAR_SIZE + BORDER_WIDTH * 2 + 4,
                              AVATAR_SIZE + BORDER_WIDTH * 2 + 4)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(50)

            self._load_photo()

        def _load_photo(self):
            if os.path.exists(PHOTO_PATH):
                self._pixmap = QPixmap(PHOTO_PATH).scaled(
                    AVATAR_SIZE, AVATAR_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                threading.Thread(target=self._download_and_reload, daemon=True).start()

        def _download_and_reload(self):
            if _download_photo():
                QTimer.singleShot(0, self._load_photo)

        def set_state(self, state: str):
            self._state = state
            self._border_color = QColor(STATE_COLORS.get(state, "#ff9e44"))
            self.update()

        def _tick(self):
            if self._state in (AvatarState.THINKING, AvatarState.SPEAKING, AvatarState.LISTENING):
                self._pulse += self._pulse_dir * 0.08
                if self._pulse >= 1.0:
                    self._pulse     = 1.0
                    self._pulse_dir = -1
                elif self._pulse <= 0.0:
                    self._pulse     = 0.0
                    self._pulse_dir = 1
            else:
                self._pulse = 0.3
            self.update()

        def paintEvent(self, event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx = self.width()  // 2
            cy = self.height() // 2
            r  = AVATAR_SIZE   // 2

            p.setBrush(QBrush(QColor("#0d0d1e")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - r - BORDER_WIDTH - 2,
                          cy - r - BORDER_WIDTH - 2,
                          (r + BORDER_WIDTH + 2) * 2,
                          (r + BORDER_WIDTH + 2) * 2)

            alpha = int(180 + self._pulse * 75)
            border_c = QColor(self._border_color)
            border_c.setAlpha(alpha)
            pen = QPen(border_c, BORDER_WIDTH)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2)

            p.setPen(Qt.PenStyle.NoPen)
            if self._pixmap:
                p.save()
                # FIX [C4]: QPainterPath импортирован статически вверху — не __import__()
                clip_path = QPainterPath()
                clip_path.addEllipse(cx - r, cy - r, r * 2, r * 2)
                p.setClipPath(clip_path)
                pw = self._pixmap.width()
                ph = self._pixmap.height()
                px = cx - pw // 2
                py = cy - ph // 2
                p.drawPixmap(px, py, self._pixmap)
                p.restore()
            else:
                p.setBrush(QBrush(QColor("#1e1e32")))
                p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
                p.setPen(QColor("#ff9e44"))
                p.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
                p.drawText(cx - r, cy - r, r * 2, r * 2,
                           Qt.AlignmentFlag.AlignCenter, "B")

            p.end()


    class AvatarOverlay(QWidget):
        """Плавающее окно аватара поверх всех окон."""

        toggle_main = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool,
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._drag_pos = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(4)

            self.avatar = BillyAvatar(self)
            layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)

            self.label = QLabel(STATE_LABELS[AvatarState.IDLE])
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setStyleSheet(
                "color:#ff9e44;font-size:10px;font-family:'Segoe UI';font-weight:bold;"
                "background:transparent;"
            )
            layout.addWidget(self.label)

            self.adjustSize()
            self._position_to_bottom_left()

        def _position_to_bottom_left(self):
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                self.move(geom.left() + 16, geom.bottom() - self.height() - 16)

        def set_state(self, state: str):
            self.avatar.set_state(state)
            self.label.setText(STATE_LABELS.get(state, "Аники"))

        def set_speaking(self, on: bool):
            self.set_state(AvatarState.SPEAKING if on else AvatarState.IDLE)

        def set_thinking(self, on: bool):
            self.set_state(AvatarState.THINKING if on else AvatarState.IDLE)

        def set_listening(self, on: bool):
            self.set_state(AvatarState.LISTENING if on else AvatarState.IDLE)

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            elif event.button() == Qt.MouseButton.RightButton:
                self.toggle_main.emit()

        def mouseMoveEvent(self, event: QMouseEvent):
            if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, _event):
            self._drag_pos = None

        def mouseDoubleClickEvent(self, _event):
            self.toggle_main.emit()
