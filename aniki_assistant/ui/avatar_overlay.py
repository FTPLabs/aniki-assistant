"""
Плавающий аватар Аники — всегда поверх окон, нижний угол экрана.
Анимирует рот когда говорит, показывает статус (думает / говорит / ждёт).
"""

import logging
import math
import random
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout, QSizePolicy
    from PyQt6.QtCore import (
        Qt, QTimer, QPoint, QRect, QRectF, pyqtSignal, QPropertyAnimation,
        QEasingCurve, QSize,
    )
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
        QLinearGradient, QPainterPath, QMouseEvent, QPixmap,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# Цвета персонажа
C_BG        = QColor("#0d0d1e")
C_SKIN      = QColor("#d4956a")
C_SKIN_DARK = QColor("#b87040")
C_HAIR      = QColor("#2a1a0a")
C_SHIRT     = QColor("#2255aa")
C_ORANGE    = QColor("#ff9e44")
C_WHITE     = QColor("#ffffff")
C_SHADOW    = QColor(0, 0, 0, 120)

AVATAR_SIZE = 140   # px — размер кружка
BORDER_W    = 3


class AvatarState:
    IDLE     = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY    = "happy"


if PYQT_AVAILABLE:

    class AvatarWidget(QWidget):
        """Рисованный аватар Аники с анимацией рта и глаз."""

        clicked = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            self._state = AvatarState.IDLE
            self._mouth_open = 0.0      # 0..1
            self._blink = 0.0           # 0..1  (1=closed)
            self._think_angle = 0
            self._happy_scale = 1.0
            self._tick = 0

            # Таймер анимации ~30fps
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick_animation)
            self._timer.start(33)

        # ── публичный API ────────────────────────────────────────────

        def set_state(self, state: str):
            self._state = state

        def set_mouth(self, value: float):
            """0=закрыт, 1=полностью открыт."""
            self._mouth_open = max(0.0, min(1.0, value))
            self.update()

        # ── анимация ─────────────────────────────────────────────────

        def _tick_animation(self):
            self._tick += 1
            changed = False

            # Моргание (каждые ~4 сек)
            if self._state != AvatarState.SPEAKING:
                cycle = self._tick % 120
                if cycle < 5:
                    self._blink = cycle / 5.0
                    changed = True
                elif cycle < 10:
                    self._blink = 1.0 - (cycle - 5) / 5.0
                    changed = True
                elif self._blink != 0.0:
                    self._blink = 0.0
                    changed = True

            # Пульсация рта при разговоре
            if self._state == AvatarState.SPEAKING:
                self._mouth_open = 0.35 + 0.35 * abs(math.sin(self._tick * 0.25))
                changed = True
            elif self._state != AvatarState.SPEAKING and self._mouth_open > 0:
                self._mouth_open = max(0.0, self._mouth_open - 0.05)
                changed = True

            # Вращение точек "думаю"
            if self._state == AvatarState.THINKING:
                self._think_angle = (self._think_angle + 6) % 360
                changed = True

            if changed:
                self.update()

        # ── рисование ────────────────────────────────────────────────

        def paintEvent(self, _event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx, cy = AVATAR_SIZE / 2, AVATAR_SIZE / 2
            r = AVATAR_SIZE / 2 - BORDER_W

            # Тень
            shadow_grad = QRadialGradient(cx + 4, cy + 4, r + 4)
            shadow_grad.setColorAt(0, QColor(0, 0, 0, 80))
            shadow_grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(shadow_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r + 4, cy - r + 4, r * 2 + 4, r * 2 + 4))

            # Кружок-фон (тёмный)
            p.setBrush(QBrush(C_BG))
            border_color = C_ORANGE if self._state == AvatarState.SPEAKING else QColor("#3a3a5e")
            p.setPen(QPen(border_color, BORDER_W))
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

            # Clip внутрь кружка
            clip_path = QPainterPath()
            clip_path.addEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
            p.setClipPath(clip_path)

            # Тело (рубашка)
            shirt_rect = QRectF(cx - r * 0.75, cy + r * 0.35, r * 1.5, r * 1.2)
            p.setBrush(QBrush(C_SHIRT))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(shirt_rect)

            # Шея
            neck_rect = QRectF(cx - r * 0.18, cy + r * 0.20, r * 0.36, r * 0.30)
            p.setBrush(QBrush(C_SKIN))
            p.drawRect(neck_rect)

            # Лицо
            face_rect = QRectF(cx - r * 0.55, cy - r * 0.65, r * 1.10, r * 1.0)
            face_grad = QRadialGradient(cx, cy - r * 0.15, r * 0.6)
            face_grad.setColorAt(0, C_SKIN)
            face_grad.setColorAt(1, C_SKIN_DARK)
            p.setBrush(QBrush(face_grad))
            p.drawEllipse(face_rect)

            # Волосы (сверху)
            hair_path = QPainterPath()
            hair_path.moveTo(cx - r * 0.55, cy - r * 0.3)
            hair_path.arcTo(face_rect, 180, 180)
            hair_path.lineTo(cx + r * 0.55, cy - r * 0.3)
            hair_path.lineTo(cx - r * 0.55, cy - r * 0.3)
            p.setBrush(QBrush(C_HAIR))
            p.drawPath(hair_path)

            # Брови
            p.setPen(QPen(C_HAIR, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            brow_y = cy - r * 0.28
            p.drawLine(QPoint(int(cx - r * 0.38), int(brow_y)),
                       QPoint(int(cx - r * 0.12), int(brow_y - r * 0.04)))
            p.drawLine(QPoint(int(cx + r * 0.12), int(brow_y - r * 0.04)),
                       QPoint(int(cx + r * 0.38), int(brow_y)))

            # Глаза
            eye_y = cy - r * 0.12
            for sign in (-1, 1):
                ex = cx + sign * r * 0.25
                ew, eh = r * 0.18, r * 0.16 * (1.0 - self._blink * 0.95)
                # белок
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(C_WHITE))
                p.drawEllipse(QRectF(ex - ew / 2, eye_y - eh / 2, ew, eh))
                # зрачок
                if eh > 2:
                    pr_size = min(ew, eh) * 0.55
                    p.setBrush(QBrush(QColor("#1a0a0a")))
                    p.drawEllipse(QRectF(ex - pr_size / 2, eye_y - pr_size / 2, pr_size, pr_size))
                    # блик
                    p.setBrush(QBrush(C_WHITE))
                    p.drawEllipse(QRectF(ex - pr_size * 0.15, eye_y - pr_size * 0.35,
                                         pr_size * 0.3, pr_size * 0.3))

            # Нос (небольшой)
            nose_x, nose_y = cx, cy + r * 0.05
            p.setPen(QPen(C_SKIN_DARK, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            nose_path = QPainterPath()
            nose_path.moveTo(nose_x - r * 0.08, nose_y - r * 0.05)
            nose_path.quadTo(nose_x, nose_y + r * 0.1,
                             nose_x + r * 0.08, nose_y - r * 0.05)
            p.drawPath(nose_path)

            # Рот
            mouth_y = cy + r * 0.22
            mouth_w = r * 0.38
            mo = self._mouth_open

            if mo < 0.05:
                # Закрытый — улыбка
                p.setPen(QPen(C_SKIN_DARK, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                mouth_path = QPainterPath()
                mouth_path.moveTo(cx - mouth_w / 2, mouth_y)
                mouth_path.quadTo(cx, mouth_y + r * 0.12, cx + mouth_w / 2, mouth_y)
                p.drawPath(mouth_path)
            else:
                # Открытый рот
                mh = r * 0.22 * mo
                mouth_rect = QRectF(cx - mouth_w / 2, mouth_y - mh / 2, mouth_w, mh)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor("#1a0a0a")))
                p.drawEllipse(mouth_rect)
                # Зубы
                if mo > 0.3:
                    teeth_rect = QRectF(cx - mouth_w * 0.4, mouth_y - mh / 2,
                                        mouth_w * 0.8, mh * 0.45)
                    p.setBrush(QBrush(C_WHITE))
                    p.drawRect(teeth_rect)

            p.setClipping(False)

            # Индикатор статуса (правый нижний угол)
            if self._state == AvatarState.THINKING:
                self._draw_thinking_dots(p, cx + r * 0.55, cy + r * 0.55)
            elif self._state == AvatarState.SPEAKING:
                self._draw_sound_bars(p, cx + r * 0.55, cy + r * 0.55)

            p.end()

        def _draw_thinking_dots(self, p: QPainter, x: float, y: float):
            """3 точки с вращением — индикатор 'думаю'."""
            for i in range(3):
                angle = math.radians(self._think_angle + i * 120)
                dx = math.cos(angle) * 8
                dy = math.sin(angle) * 8
                alpha = int(255 * (0.3 + 0.7 * ((i + self._think_angle // 30) % 3 == 0)))
                p.setBrush(QBrush(QColor(255, 158, 68, alpha)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(x + dx - 3, y + dy - 3, 6, 6))

        def _draw_sound_bars(self, p: QPainter, x: float, y: float):
            """Анимированные полоски — индикатор речи."""
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(3):
                h = 4 + 8 * abs(math.sin(self._tick * 0.3 + i * 1.2))
                p.setBrush(QBrush(C_ORANGE))
                p.drawRect(QRectF(x - 7 + i * 6, y - h / 2, 4, h))

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()


    class AvatarOverlay(QWidget):
        """
        Плавающее окно поверх всего — показывает аватар Аники.
        Кликабельное: открывает/скрывает главное окно.
        """
        toggle_main = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(
                parent,
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool,
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setFixedSize(AVATAR_SIZE + 20, AVATAR_SIZE + 50)

            self._drag_pos: Optional[QPoint] = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 0, 10, 0)
            layout.setSpacing(0)

            self.avatar = AvatarWidget()
            self.avatar.clicked.connect(self.toggle_main.emit)
            layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)

            self.label = QLabel("Аники")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setStyleSheet(
                "color: #ff9e44; font-size: 11px; font-weight: bold; "
                "font-family: 'Segoe UI'; background: transparent;"
            )
            layout.addWidget(self.label)

            # Позиция: нижний левый угол
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                self.move(geom.left() + 16, geom.bottom() - self.height() - 16)

        def set_state(self, state: str):
            self.avatar.set_state(state)
            labels = {
                AvatarState.IDLE:     "Аники",
                AvatarState.THINKING: "Думаю...",
                AvatarState.SPEAKING: "Говорю!",
                AvatarState.HAPPY:    "Yeah buddy!",
            }
            self.label.setText(labels.get(state, "Аники"))

        def set_speaking(self, is_speaking: bool):
            self.set_state(AvatarState.SPEAKING if is_speaking else AvatarState.IDLE)

        def set_thinking(self, is_thinking: bool):
            self.set_state(AvatarState.THINKING if is_thinking else AvatarState.IDLE)

        # ── drag ─────────────────────────────────────────────────────

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, event: QMouseEvent):
            if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, _event):
            self._drag_pos = None
