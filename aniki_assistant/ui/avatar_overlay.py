"""
Плавающий аватар Аники (Билли Херрингтон) — всегда поверх окон.
Нарисован вручную через QPainter: узнаваемые черты Билли —
широкие брови, густые усы, квадратная челюсть, короткие тёмные волосы.
Состояния: idle, thinking, speaking, listening.
"""

import logging
import math
import random
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout
    from PyQt6.QtCore import (
        Qt, QTimer, QPoint, QRectF, pyqtSignal, QSize,
    )
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
        QLinearGradient, QPainterPath, QMouseEvent,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# ── Цветовая палитра Билли ───────────────────────────────────────────────────
C_BG         = QColor("#0d0d1e")
C_SKIN       = QColor("#c8845a")     # загорелая кожа
C_SKIN_D     = QColor("#a06040")     # тень
C_SKIN_L     = QColor("#dda070")     # светлые блики
C_HAIR       = QColor("#1a0e06")     # очень тёмные волосы
C_MUSTACHE   = QColor("#111106")     # чёрно-тёмные усы
C_EYE_W      = QColor("#f0f0ec")
C_IRIS       = QColor("#3d2510")     # карие глаза
C_PUPIL      = QColor("#0a0604")
C_LEATHER    = QColor("#1a0d08")     # кожаная куртка
C_LEATHER_S  = QColor("#2d1a10")
C_ORANGE     = QColor("#ff9e44")
C_WHITE      = QColor("#ffffff")
C_LISTEN     = QColor("#44aaff")     # синий — режим слушания

AVATAR_SIZE = 150
BORDER_W    = 3


class AvatarState:
    IDLE      = "idle"
    THINKING  = "thinking"
    SPEAKING  = "speaking"
    LISTENING = "listening"
    HAPPY     = "happy"


if PYQT_AVAILABLE:

    class AvatarWidget(QWidget):
        """Рисованный аватар Билли Херрингтона с анимацией."""

        clicked = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            self._state        = AvatarState.IDLE
            self._mouth_open   = 0.0
            self._blink        = 0.0
            self._think_angle  = 0
            self._tick         = 0
            self._listen_pulse = 0.0
            self._listen_dir   = 1

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick_animation)
            self._timer.start(33)

        def set_state(self, state: str):
            self._state = state

        def set_mouth(self, value: float):
            self._mouth_open = max(0.0, min(1.0, value))
            self.update()

        def _tick_animation(self):
            self._tick += 1
            changed = False

            # Моргание (каждые ~4 с)
            if self._state not in (AvatarState.SPEAKING, AvatarState.LISTENING):
                cycle = self._tick % 130
                if cycle < 5:
                    self._blink = cycle / 5.0; changed = True
                elif cycle < 10:
                    self._blink = 1.0 - (cycle - 5) / 5.0; changed = True
                elif self._blink != 0.0:
                    self._blink = 0.0; changed = True

            # Рот при разговоре
            if self._state == AvatarState.SPEAKING:
                self._mouth_open = 0.3 + 0.38 * abs(math.sin(self._tick * 0.28))
                changed = True
            elif self._mouth_open > 0:
                self._mouth_open = max(0.0, self._mouth_open - 0.06)
                changed = True

            # Вращение точек "думаю"
            if self._state == AvatarState.THINKING:
                self._think_angle = (self._think_angle + 7) % 360
                changed = True

            # Пульс режима слушания
            if self._state == AvatarState.LISTENING:
                self._listen_pulse += 0.07 * self._listen_dir
                if self._listen_pulse >= 1.0:
                    self._listen_dir = -1
                elif self._listen_pulse <= 0.0:
                    self._listen_dir = 1
                changed = True

            if changed:
                self.update()

        # ── Отрисовка ─────────────────────────────────────────────────────────

        def paintEvent(self, _event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            cx  = AVATAR_SIZE / 2
            cy  = AVATAR_SIZE / 2
            r   = AVATAR_SIZE / 2 - BORDER_W - 2

            self._draw_shadow(p, cx, cy, r)
            self._draw_circle_bg(p, cx, cy, r)
            self._clip_to_circle(p, cx, cy, r)
            self._draw_body(p, cx, cy, r)
            self._draw_neck(p, cx, cy, r)
            self._draw_face(p, cx, cy, r)
            self._draw_hair(p, cx, cy, r)
            self._draw_brows(p, cx, cy, r)
            self._draw_eyes(p, cx, cy, r)
            self._draw_nose(p, cx, cy, r)
            self._draw_mustache(p, cx, cy, r)
            self._draw_mouth(p, cx, cy, r)
            p.setClipping(False)
            self._draw_status(p, cx, cy, r)
            p.end()

        def _draw_shadow(self, p, cx, cy, r):
            g = QRadialGradient(cx + 5, cy + 5, r + 6)
            g.setColorAt(0, QColor(0, 0, 0, 90))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r + 4, cy - r + 4, r * 2 + 6, r * 2 + 6))

        def _draw_circle_bg(self, p, cx, cy, r):
            p.setBrush(QBrush(C_BG))
            if self._state == AvatarState.SPEAKING:
                border = C_ORANGE
            elif self._state == AvatarState.LISTENING:
                alpha = int(140 + 115 * self._listen_pulse)
                border = QColor(68, 170, 255, alpha)
            elif self._state == AvatarState.THINKING:
                border = QColor("#aa5500")
            else:
                border = QColor("#3a3a5e")
            p.setPen(QPen(border, BORDER_W))
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        def _clip_to_circle(self, p, cx, cy, r):
            clip = QPainterPath()
            clip.addEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
            p.setClipPath(clip)

        def _draw_body(self, p, cx, cy, r):
            # Кожаная куртка — массивный силуэт (Билли широкоплечий)
            p.setPen(Qt.PenStyle.NoPen)
            body = QPainterPath()
            body.moveTo(cx - r * 0.95, cy + r)
            body.lineTo(cx - r * 0.95, cy + r * 0.45)
            body.quadTo(cx - r * 0.6, cy + r * 0.15, cx - r * 0.22, cy + r * 0.28)
            body.lineTo(cx + r * 0.22, cy + r * 0.28)
            body.quadTo(cx + r * 0.6, cy + r * 0.15, cx + r * 0.95, cy + r * 0.45)
            body.lineTo(cx + r * 0.95, cy + r)
            body.closeSubpath()
            # Кожа куртки — тёмная + небольшой блик
            g = QLinearGradient(cx - r, cy + r * 0.4, cx + r, cy + r * 0.4)
            g.setColorAt(0.0, C_LEATHER)
            g.setColorAt(0.3, C_LEATHER_S)
            g.setColorAt(0.7, C_LEATHER_S)
            g.setColorAt(1.0, C_LEATHER)
            p.setBrush(QBrush(g))
            p.drawPath(body)

        def _draw_neck(self, p, cx, cy, r):
            p.setPen(Qt.PenStyle.NoPen)
            # Широкая шея — Билли накачан
            nw = r * 0.30
            nh = r * 0.28
            ny = cy + r * 0.20
            neck_path = QPainterPath()
            neck_path.addRect(QRectF(cx - nw / 2, ny, nw, nh))
            p.setBrush(QBrush(C_SKIN))
            p.drawPath(neck_path)

        def _draw_face(self, p, cx, cy, r):
            # Квадратная сильная челюсть — отличительная черта Билли
            p.setPen(Qt.PenStyle.NoPen)
            fw = r * 1.05
            fh = r * 0.98
            fy = cy - r * 0.62

            face_path = QPainterPath()
            # Верх — скруглённый, низ — почти прямой (квадратная челюсть)
            face_path.moveTo(cx - fw * 0.48, fy + fh * 0.55)
            face_path.lineTo(cx - fw * 0.50, fy + fh * 0.80)
            # Угол челюсти
            face_path.quadTo(cx - fw * 0.50, fy + fh, cx - fw * 0.30, fy + fh)
            face_path.lineTo(cx + fw * 0.30, fy + fh)
            face_path.quadTo(cx + fw * 0.50, fy + fh, cx + fw * 0.50, fy + fh * 0.80)
            face_path.lineTo(cx + fw * 0.48, fy + fh * 0.55)
            # Верхняя часть — дуга
            face_path.quadTo(cx + fw * 0.52, fy - fh * 0.05, cx, fy - fh * 0.02)
            face_path.quadTo(cx - fw * 0.52, fy - fh * 0.05, cx - fw * 0.48, fy + fh * 0.55)
            face_path.closeSubpath()

            g = QRadialGradient(cx, cy - r * 0.10, r * 0.65)
            g.setColorAt(0, C_SKIN_L)
            g.setColorAt(0.5, C_SKIN)
            g.setColorAt(1, C_SKIN_D)
            p.setBrush(QBrush(g))
            p.drawPath(face_path)

        def _draw_hair(self, p, cx, cy, r):
            # Короткие тёмные волосы — почти под ноль сверху
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(C_HAIR))
            fy = cy - r * 0.62
            hair_path = QPainterPath()
            hair_path.moveTo(cx - r * 0.52, fy + r * 0.45)
            hair_path.arcTo(QRectF(cx - r * 0.53, fy, r * 1.06, r * 0.90), 180, 180)
            hair_path.lineTo(cx + r * 0.52, fy + r * 0.45)
            hair_path.lineTo(cx + r * 0.48, fy + r * 0.38)
            hair_path.arcTo(QRectF(cx - r * 0.48, fy + r * 0.04, r * 0.96, r * 0.70), 0, -180)
            hair_path.closeSubpath()
            p.drawPath(hair_path)

        def _draw_brows(self, p, cx, cy, r):
            # Густые тёмные брови — очень характерные для Билли
            p.setPen(QPen(C_HAIR, r * 0.07, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            brow_y = cy - r * 0.26
            # Левая бровь — слегка наклонена
            lp = QPainterPath()
            lp.moveTo(cx - r * 0.44, brow_y + r * 0.02)
            lp.quadTo(cx - r * 0.28, brow_y - r * 0.04, cx - r * 0.10, brow_y)
            p.drawPath(lp)
            # Правая бровь
            rp = QPainterPath()
            rp.moveTo(cx + r * 0.10, brow_y)
            rp.quadTo(cx + r * 0.28, brow_y - r * 0.04, cx + r * 0.44, brow_y + r * 0.02)
            p.drawPath(rp)

        def _draw_eyes(self, p, cx, cy, r):
            eye_y = cy - r * 0.11
            for sign in (-1, 1):
                ex = cx + sign * r * 0.26
                ew = r * 0.20
                eh = r * 0.14 * (1.0 - self._blink * 0.96)
                if eh < 1:
                    eh = 1

                p.setPen(Qt.PenStyle.NoPen)

                # Белок
                p.setBrush(QBrush(C_EYE_W))
                p.drawEllipse(QRectF(ex - ew / 2, eye_y - eh / 2, ew, eh))

                if eh > 2:
                    # Радужка
                    ir = min(ew, eh) * 0.55
                    p.setBrush(QBrush(C_IRIS))
                    p.drawEllipse(QRectF(ex - ir / 2, eye_y - ir / 2, ir, ir))
                    # Зрачок
                    pr = ir * 0.55
                    p.setBrush(QBrush(C_PUPIL))
                    p.drawEllipse(QRectF(ex - pr / 2, eye_y - pr / 2, pr, pr))
                    # Блик
                    p.setBrush(QBrush(C_WHITE))
                    p.drawEllipse(QRectF(ex - pr * 0.15,
                                         eye_y - pr * 0.38,
                                         pr * 0.32, pr * 0.32))

        def _draw_nose(self, p, cx, cy, r):
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(C_SKIN_D, 1.8, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            ny = cy + r * 0.05
            np_ = QPainterPath()
            np_.moveTo(cx - r * 0.06, ny - r * 0.08)
            np_.quadTo(cx, ny + r * 0.12, cx + r * 0.06, ny - r * 0.08)
            p.drawPath(np_)
            # Ноздри
            p.setPen(QPen(C_SKIN_D, 1.2))
            p.drawLine(QPoint(int(cx - r * 0.10), int(ny + r * 0.04)),
                       QPoint(int(cx - r * 0.06), int(ny + r * 0.02)))
            p.drawLine(QPoint(int(cx + r * 0.10), int(ny + r * 0.04)),
                       QPoint(int(cx + r * 0.06), int(ny + r * 0.02)))

        def _draw_mustache(self, p, cx, cy, r):
            """Густые висячие усы — главная черта Билли."""
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(C_MUSTACHE))

            my = cy + r * 0.16        # вертикальный центр усов
            mw = r * 0.46             # полуширина
            mh_top = r * 0.08         # высота верхней части
            mh_bot = r * 0.14         # высота нижних кончиков

            mpath = QPainterPath()
            # Верхний контур — прямой
            mpath.moveTo(cx - mw, my - mh_top)
            mpath.lineTo(cx + mw, my - mh_top)
            # Правый кончик — загнут вниз
            mpath.quadTo(cx + mw + r * 0.06, my + mh_bot * 0.3,
                         cx + mw - r * 0.04, my + mh_bot)
            # Середина — небольшая вмятина над губой
            mpath.quadTo(cx + r * 0.14, my + r * 0.04,
                         cx, my + r * 0.06)
            mpath.quadTo(cx - r * 0.14, my + r * 0.04,
                         cx - mw + r * 0.04, my + mh_bot)
            # Левый кончик
            mpath.quadTo(cx - mw - r * 0.06, my + mh_bot * 0.3,
                         cx - mw, my - mh_top)
            mpath.closeSubpath()
            p.drawPath(mpath)

            # Небольшой блик на усах (объём)
            p.setBrush(QBrush(QColor(60, 40, 20, 60)))
            hl_path = QPainterPath()
            hl_path.addEllipse(QRectF(cx - mw * 0.6, my - mh_top,
                                       mw * 1.2, mh_top * 0.7))
            p.drawPath(hl_path)

        def _draw_mouth(self, p, cx, cy, r):
            mouth_y = cy + r * 0.35
            mouth_w = r * 0.34
            mo = self._mouth_open

            if mo < 0.05:
                # Слегка поджатые губы — серьёзная мина Билли
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(C_SKIN_D, 2.2, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                m = QPainterPath()
                m.moveTo(cx - mouth_w / 2, mouth_y)
                m.quadTo(cx, mouth_y + r * 0.06, cx + mouth_w / 2, mouth_y)
                p.drawPath(m)
            else:
                mh = r * 0.20 * mo
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor("#150808")))
                p.drawEllipse(QRectF(cx - mouth_w / 2, mouth_y - mh / 2,
                                      mouth_w, mh))
                if mo > 0.25:
                    p.setBrush(QBrush(C_WHITE))
                    p.drawRect(QRectF(cx - mouth_w * 0.36,
                                      mouth_y - mh / 2,
                                      mouth_w * 0.72, mh * 0.4))

        def _draw_status(self, p, cx, cy, r):
            if self._state == AvatarState.THINKING:
                self._draw_thinking_dots(p, cx + r * 0.58, cy + r * 0.58)
            elif self._state == AvatarState.SPEAKING:
                self._draw_sound_bars(p, cx + r * 0.58, cy + r * 0.58)
            elif self._state == AvatarState.LISTENING:
                self._draw_listening_ring(p, cx, cy, r)

        def _draw_thinking_dots(self, p, x, y):
            for i in range(3):
                angle = math.radians(self._think_angle + i * 120)
                dx = math.cos(angle) * 9
                dy = math.sin(angle) * 9
                alpha = int(255 * (0.3 + 0.7 * ((i + self._think_angle // 30) % 3 == 0)))
                p.setBrush(QBrush(QColor(255, 158, 68, alpha)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(x + dx - 3.5, y + dy - 3.5, 7, 7))

        def _draw_sound_bars(self, p, x, y):
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(3):
                h = 5 + 9 * abs(math.sin(self._tick * 0.32 + i * 1.3))
                p.setBrush(QBrush(C_ORANGE))
                p.drawRect(QRectF(x - 8 + i * 7, y - h / 2, 5, h))

        def _draw_listening_ring(self, p, cx, cy, r):
            alpha = int(80 + 100 * self._listen_pulse)
            pen_color = QColor(68, 170, 255, alpha)
            pen_width = 3 + 2 * self._listen_pulse
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(pen_color, pen_width))
            margin = BORDER_W + 2
            p.drawEllipse(QRectF(margin, margin,
                                  AVATAR_SIZE - 2 * margin,
                                  AVATAR_SIZE - 2 * margin))

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()


    class AvatarOverlay(QWidget):
        """Плавающее окно Билли Херрингтона поверх всего."""

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
            self.setFixedSize(AVATAR_SIZE + 20, AVATAR_SIZE + 48)

            self._drag_pos: Optional[QPoint] = None

            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 0, 10, 0)
            layout.setSpacing(2)

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

            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                self.move(geom.left() + 16, geom.bottom() - self.height() - 16)

        def set_state(self, state: str):
            self.avatar.set_state(state)
            labels = {
                AvatarState.IDLE:      "Аники",
                AvatarState.THINKING:  "Думаю...",
                AvatarState.SPEAKING:  "Говорю!",
                AvatarState.LISTENING: "Слушаю...",
                AvatarState.HAPPY:     "Yeah buddy!",
            }
            self.label.setText(labels.get(state, "Аники"))

        def set_speaking(self, is_speaking: bool):
            self.set_state(AvatarState.SPEAKING if is_speaking else AvatarState.IDLE)

        def set_thinking(self, is_thinking: bool):
            self.set_state(AvatarState.THINKING if is_thinking else AvatarState.IDLE)

        def set_listening(self, is_listening: bool):
            self.set_state(AvatarState.LISTENING if is_listening else AvatarState.IDLE)

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, event: QMouseEvent):
            if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, _event):
            self._drag_pos = None
