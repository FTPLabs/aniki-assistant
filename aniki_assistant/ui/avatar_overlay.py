"""
Аватар Аники v3.1 — живая анимация, не просто круг!
Полностью переработан: пульс, свечение, частицы, состояния.
"""

import math
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication, QMenu, QSizeGrip
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QRectF, QPointF,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QFont, QFontMetrics, QPainterPath,
    QMouseEvent, QContextMenuEvent, QPixmap,
)

logger = logging.getLogger(__name__)

# ── Цветовая палитра ──────────────────────────────────────────────────────────
C_BG        = QColor(13, 13, 30, 220)
C_IDLE      = QColor(255, 158, 68)       # оранжевый
C_THINK     = QColor(100, 180, 255)      # голубой
C_SPEAK     = QColor(80, 230, 150)       # зелёный
C_LISTEN    = QColor(200, 100, 255)      # фиолетовый
C_GLOW_IDLE = QColor(255, 158, 68, 60)
C_GLOW_THINK= QColor(100, 180, 255, 60)
C_GLOW_SPEAK= QColor(80, 230, 150, 60)
C_GLOW_LIST = QColor(200, 100, 255, 60)


class AvatarCanvas(QWidget):
    """Холст аватара с полной анимацией."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self._state    = "idle"
        self._tick     = 0.0
        self._bars     = [0.0] * 8      # эквалайзер для speak
        self._particles= []             # список частиц
        self._init_particles()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(33)  # ~30 fps

    def _init_particles(self):
        import random
        self._particles = []
        for _ in range(12):
            angle  = random.uniform(0, 2 * math.pi)
            radius = random.uniform(38, 55)
            speed  = random.uniform(0.01, 0.03)
            size   = random.uniform(2, 5)
            alpha  = random.uniform(40, 150)
            self._particles.append({
                "angle": angle, "radius": radius,
                "speed": speed, "size": size, "alpha": alpha,
            })

    def _update(self):
        import random
        self._tick += 0.05
        # Обновляем частицы
        for p in self._particles:
            p["angle"] += p["speed"]
        # Обновляем эквалайзер
        if self._state == "speak":
            for i in range(len(self._bars)):
                target = random.uniform(0.3, 1.0)
                self._bars[i] += (target - self._bars[i]) * 0.3
        else:
            for i in range(len(self._bars)):
                self._bars[i] *= 0.85
        self.update()

    def set_state(self, state: str):
        self._state = state

    def _color_for_state(self):
        return {
            "idle":    (C_IDLE,   C_GLOW_IDLE),
            "think":   (C_THINK,  C_GLOW_THINK),
            "speak":   (C_SPEAK,  C_GLOW_SPEAK),
            "listen":  (C_LISTEN, C_GLOW_LIST),
        }.get(self._state, (C_IDLE, C_GLOW_IDLE))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        col, glow_col = self._color_for_state()

        # ── 1. Внешнее свечение (пульс) ───────────────────────────────────
        pulse = 0.5 + 0.5 * math.sin(self._tick * 1.5)
        glow_r = 48 + pulse * 8
        grad = QRadialGradient(cx, cy, glow_r)
        glow_a = QColor(glow_col)
        glow_a.setAlpha(int(80 + pulse * 60))
        grad.setColorAt(0.0, glow_a)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # ── 2. Частицы ────────────────────────────────────────────────────
        for pt in self._particles:
            px = cx + math.cos(pt["angle"]) * pt["radius"]
            py = cy + math.sin(pt["angle"]) * pt["radius"]
            pc = QColor(col)
            pc.setAlpha(int(pt["alpha"]))
            p.setBrush(QBrush(pc))
            p.setPen(Qt.PenStyle.NoPen)
            sz = pt["size"]
            p.drawEllipse(QRectF(px - sz / 2, py - sz / 2, sz, sz))

        # ── 3. Кольцо-граница (вращающееся) ──────────────────────────────
        ring_rect = QRectF(cx - 44, cy - 44, 88, 88)
        pen = QPen(col, 2.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.translate(cx, cy)
        p.rotate(self._tick * 30 % 360)
        p.drawEllipse(QRectF(-44, -44, 88, 88))
        p.restore()

        # ── 4. Тёмный фон аватара ─────────────────────────────────────────
        bg_grad = QRadialGradient(cx, cy - 5, 36)
        bg_grad.setColorAt(0.0, QColor(30, 25, 60))
        bg_grad.setColorAt(1.0, QColor(13, 13, 30))
        p.setBrush(QBrush(bg_grad))
        p.setPen(QPen(col, 2))
        p.drawEllipse(QRectF(cx - 38, cy - 38, 76, 76))

        # ── 5. Эквалайзер (только в режиме speak) ────────────────────────
        if self._state == "speak":
            bar_w  = 5
            bar_gap = 3
            n_bars = len(self._bars)
            total  = n_bars * bar_w + (n_bars - 1) * bar_gap
            bx     = cx - total / 2
            for i, bar_h_norm in enumerate(self._bars):
                bh = max(3, bar_h_norm * 24)
                br = QRectF(bx + i * (bar_w + bar_gap), cy - bh / 2, bar_w, bh)
                bc = QColor(col)
                bc.setAlpha(200)
                p.setBrush(QBrush(bc))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(br, 2, 2)
        else:
            # ── 6. Буква «Б» или иконка состояния ───────────────────────
            label_map = {
                "idle":  "A",
                "think": "...",
                "listen": "🎤",
            }
            label = label_map.get(self._state, "A")

            if self._state == "think":
                # Три точки с мигающей анимацией
                dot_r = 5.0
                dots_y = cy + 2
                for i, off in enumerate([-12, 0, 12]):
                    phase = math.sin(self._tick * 4 + i * 1.2)
                    a = int(120 + phase * 120)
                    dc = QColor(col)
                    dc.setAlpha(a)
                    p.setBrush(QBrush(dc))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QRectF(cx + off - dot_r / 2, dots_y - dot_r / 2, dot_r, dot_r))
            elif self._state == "listen":
                # Волна
                wave_path = QPainterPath()
                pts = 20
                for i in range(pts + 1):
                    fx = cx - 18 + i * (36 / pts)
                    fy = cy + math.sin(self._tick * 6 + i * 0.8) * 8
                    if i == 0:
                        wave_path.moveTo(fx, fy)
                    else:
                        wave_path.lineTo(fx, fy)
                wave_pen = QPen(col, 2.5)
                wave_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(wave_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(wave_path)
            else:
                # Idle — большая буква А
                font = QFont("Segoe UI", 26, QFont.Weight.Bold)
                p.setFont(font)
                fc = QColor(col)
                fc.setAlpha(220)
                p.setPen(fc)
                p.drawText(QRectF(cx - 20, cy - 20, 40, 40),
                           Qt.AlignmentFlag.AlignCenter, "A")

        p.end()


class AvatarOverlay(QWidget):
    """Плавающий аватар поверх всех окон."""

    toggle_main = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._canvas = AvatarCanvas(self)
        self._label  = QLabel("Аники", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color:#ff9e44;font-size:11px;font-weight:bold;"
            "font-family:'Segoe UI';background:transparent;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(130, 145)

        # Позиция — правый нижний угол
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 145, screen.height() - 160)

        self._drag_pos: Optional[QPoint] = None

    # ── Состояния ─────────────────────────────────────────────────────────────
    def set_thinking(self, on: bool):
        self._canvas.set_state("think" if on else "idle")

    def set_speaking(self, on: bool):
        self._canvas.set_state("speak" if on else "idle")

    def set_listening(self, on: bool):
        self._canvas.set_state("listen" if on else "idle")

    # ── Мышь — перетаскивание и клик ─────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos:
                dist = (e.globalPosition().toPoint() - self._drag_pos - self.pos()).manhattanLength()
                if dist < 5:
                    self.toggle_main.emit()
            self._drag_pos = None

    def contextMenuEvent(self, e: QContextMenuEvent):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1a1a2e;color:#e8e8f0;border:1px solid #ff9e44;border-radius:8px;}"
            "QMenu::item:selected{background:#ff9e44;color:#0d0d1e;}"
        )
        menu.addAction("💬 Открыть чат",    lambda: self.toggle_main.emit())
        menu.addSeparator()
        menu.addAction("❌ Закрыть аватар", self.close)
        menu.exec(e.globalPos())
