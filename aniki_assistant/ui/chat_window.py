"""
ChatWindow Аники v3.1 — полностью переработанный интерфейс.
Живые анимации, градиенты, современный дизайн.
"""

import logging
from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea, QFrame, QTabWidget, QSizePolicy,
    QGraphicsOpacityEffect, QApplication, QScrollBar,
    QListWidget, QListWidgetItem, QDialog, QLineEdit,
    QSpinBox, QFormLayout, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QSize, QThread, QObject, QEvent,
)
from PyQt6.QtGui import (
    QFont, QColor, QKeyEvent, QIcon, QPixmap, QPainter,
    QLinearGradient, QPainterPath, QBrush, QPen,
)

logger = logging.getLogger(__name__)

# ── Стили ────────────────────────────────────────────────────────────────────
STYLE_MAIN = """
QWidget {
    background: #0d0d1e;
    color: #e8e8f0;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #ff9e44;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollArea { border: none; background: transparent; }
QTabWidget::pane { border: 1px solid #2a2a4a; border-radius: 8px; }
QTabBar::tab {
    background: #1a1a2e;
    color: #888;
    padding: 8px 20px;
    border-radius: 6px 6px 0 0;
    font-size: 13px;
}
QTabBar::tab:selected { background: #252545; color: #ff9e44; }
QTabBar::tab:hover { color: #e8e8f0; }
"""

STYLE_INPUT = """
QTextEdit {
    background: #1a1a2e;
    color: #e8e8f0;
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 10px 16px;
    font-size: 14px;
    font-family: 'Segoe UI', Arial;
    selection-background-color: #ff9e44;
}
QTextEdit:focus {
    border: 1px solid #ff9e44;
}
"""

STYLE_BTN_SEND = """
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #ff9e44, stop:1 #ff6b1a);
    color: #0d0d1e;
    border: none;
    border-radius: 22px;
    font-size: 18px;
    font-weight: bold;
    min-width: 44px;
    min-height: 44px;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #ffb866, stop:1 #ff8833);
}
QPushButton:pressed { background: #cc7a33; }
"""

STYLE_BTN_MIC = """
QPushButton {
    background: #1e1e3a;
    color: #ff9e44;
    border: 1.5px solid #ff9e44;
    border-radius: 22px;
    font-size: 16px;
    min-width: 44px;
    min-height: 44px;
}
QPushButton:hover { background: #2a2a4e; }
QPushButton:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #c060ff, stop:1 #8020cc);
    border-color: #c060ff;
    color: white;
}
"""


# ── Пузырь сообщения ──────────────────────────────────────────────────────────
class MessageBubble(QFrame):
    def __init__(self, text: str, is_bot: bool, parent=None):
        super().__init__(parent)
        self.is_bot = is_bot
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(350)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        # Имя
        name = "Аники" if is_bot else "Ты"
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{'#ff9e44' if is_bot else '#7eb8ff'};"
            "font-size:11px;font-weight:bold;background:transparent;padding:0 4px;"
        )

        # Текст
        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_lbl.setStyleSheet(
            f"""
            background: {'#1e1e3a' if is_bot else '#1a2e1a'};
            color: #e8e8f0;
            border-radius: 14px;
            padding: 10px 14px;
            font-size: 14px;
            border: 1px solid {'#2a2a5a' if is_bot else '#1a3a1a'};
            """
        )
        msg_lbl.setMaximumWidth(420)

        # Время
        time_lbl = QLabel(datetime.now().strftime("%H:%M"))
        time_lbl.setStyleSheet("color:#444;font-size:10px;background:transparent;padding:0 4px;")

        if is_bot:
            layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(msg_lbl, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(time_lbl, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(msg_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addWidget(time_lbl, alignment=Qt.AlignmentFlag.AlignRight)

        self._anim.start()

    def append_text(self, chunk: str):
        # Для стриминга — находим QLabel с сообщением и обновляем
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if isinstance(w, QLabel) and "background: #1e1e3a" in (w.styleSheet() or ""):
                w.setText(w.text() + chunk)
                return


# ── Статусная строка ──────────────────────────────────────────────────────────
class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color:#50e690;font-size:10px;")
        self._text = QLabel("Онлайн")
        self._text.setStyleSheet("color:#50e690;font-size:12px;")

        layout.addStretch()
        layout.addWidget(self._dot)
        layout.addWidget(self._text)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_on = True

    def set_status(self, text: str, color: str = "#50e690", blink: bool = False):
        self._text.setText(text)
        self._dot.setStyleSheet(f"color:{color};font-size:10px;")
        self._text.setStyleSheet(f"color:{color};font-size:12px;")
        if blink:
            self._blink_timer.start(600)
        else:
            self._blink_timer.stop()
            self._dot.setVisible(True)

    def _blink(self):
        self._blink_on = not self._blink_on
        self._dot.setVisible(self._blink_on)


# ── Рабочий поток для ИИ ─────────────────────────────────────────────────────
class AIWorker(QObject):
    token_ready    = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    error          = pyqtSignal(str)
    finished       = pyqtSignal()

    def __init__(self, ai_engine, text: str, parent=None):
        super().__init__(parent)
        self._ai  = ai_engine
        self._text = text

    def run(self):
        try:
            full = ""
            for token in self._ai.chat_stream(self._text):
                self.token_ready.emit(token)
                full += token
            self.response_ready.emit(full)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


# ── Основное окно ─────────────────────────────────────────────────────────────
class ChatWindow(QWidget):
    avatar_thinking = pyqtSignal(bool)
    avatar_speaking = pyqtSignal(bool)
    avatar_listening= pyqtSignal(bool)

    def __init__(self, ai_engine=None, reminder_system=None,
                 tts_enabled=True, stt_enabled=False, parent=None):
        super().__init__(parent)
        self.ai_engine       = ai_engine
        self.reminder_system = reminder_system
        self.tts_enabled     = tts_enabled
        self.stt_enabled     = stt_enabled
        self._mic_active     = False
        self._current_bubble : Optional[MessageBubble] = None
        self._ai_thread: Optional[QThread] = None

        self._setup_window()
        self._setup_ui()
        self.setStyleSheet(STYLE_MAIN)
        QTimer.singleShot(100, self._welcome)

    def _setup_window(self):
        self.setWindowTitle("Аники — ИИ-ассистент")
        self.resize(800, 640)
        self.setMinimumSize(480, 360)
        try:
            pix = QPixmap(32, 32)
            pix.fill(QColor(13, 13, 30))
            p = QPainter(pix)
            p.setPen(QColor("#ff9e44"))
            p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "A")
            p.end()
            self.setWindowIcon(QIcon(pix))
        except Exception:
            pass

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Заголовок ─────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0d0d1e,stop:0.5 #1a0a2e,stop:1 #0d0d1e);"
            "border-bottom: 1px solid #2a2a4a;"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel("АНИКИ")
        title_lbl.setStyleSheet(
            "color:#ff9e44;font-size:22px;font-weight:900;"
            "letter-spacing:4px;font-family:'Segoe UI';background:transparent;"
        )
        self._status_bar = StatusBar()

        h_lay.addWidget(title_lbl)
        h_lay.addStretch()
        h_lay.addWidget(self._status_bar)

        root.addWidget(header)

        # ── Вкладки ───────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        root.addWidget(tabs)

        # Вкладка «Чат»
        chat_tab = QWidget()
        chat_lay = QVBoxLayout(chat_tab)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(0)

        # Область сообщений
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: #0d0d1e;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(16, 16, 16, 16)
        self._msg_layout.setSpacing(6)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        chat_lay.addWidget(self._scroll)

        # Индикатор «печатает...»
        self._typing_label = QLabel("Аники думает...")
        self._typing_label.setStyleSheet(
            "color:#ff9e44;font-size:12px;font-style:italic;"
            "background:#0d0d1e;padding:4px 20px;"
        )
        self._typing_label.hide()
        chat_lay.addWidget(self._typing_label)

        # Панель ввода
        input_panel = QWidget()
        input_panel.setStyleSheet(
            "background:#111128;border-top:1px solid #2a2a4a;"
        )
        inp_lay = QHBoxLayout(input_panel)
        inp_lay.setContentsMargins(12, 10, 12, 10)
        inp_lay.setSpacing(8)

        self._input = QTextEdit()
        self._input.setStyleSheet(STYLE_INPUT)
        self._input.setPlaceholderText("Напиши Аники или говори в микрофон...")
        self._input.setFixedHeight(44)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input.installEventFilter(self)

        self._btn_mic = QPushButton("🎤")
        self._btn_mic.setStyleSheet(STYLE_BTN_MIC)
        self._btn_mic.setCheckable(True)
        self._btn_mic.setToolTip("Голосовой ввод")
        self._btn_mic.setFixedSize(44, 44)
        self._btn_mic.setVisible(self.stt_enabled)
        self._btn_mic.toggled.connect(self._toggle_mic)

        self._btn_send = QPushButton("➤")
        self._btn_send.setStyleSheet(STYLE_BTN_SEND)
        self._btn_send.setFixedSize(44, 44)
        self._btn_send.setToolTip("Отправить (Enter)")
        self._btn_send.clicked.connect(self._send_message)

        inp_lay.addWidget(self._input)
        if self.stt_enabled:
            inp_lay.addWidget(self._btn_mic)
        inp_lay.addWidget(self._btn_send)

        chat_lay.addWidget(input_panel)
        tabs.addTab(chat_tab, "💬  Чат")

        # Вкладка «Напоминания»
        from .reminder_tab import ReminderTab
        try:
            self._reminder_tab = ReminderTab(self.reminder_system)
            tabs.addTab(self._reminder_tab, "🔔  Напоминания")
        except Exception:
            tabs.addTab(QWidget(), "🔔  Напоминания")

        # Вкладка «Настройки»
        tabs.addTab(self._make_settings_tab(), "⚙️  Настройки")

        self._tabs = tabs

    def _make_settings_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        def row(lbl, wgt):
            r = QHBoxLayout()
            l = QLabel(lbl)
            l.setStyleSheet("color:#aaa;font-size:13px;")
            l.setFixedWidth(160)
            r.addWidget(l)
            r.addWidget(wgt)
            lay.addLayout(r)

        from PyQt6.QtWidgets import QComboBox, QCheckBox, QSlider
        from PyQt6.QtCore import Qt as _Qt

        voice_cb = QComboBox()
        voice_cb.addItems(["Silero (Айдар)", "XTTS-v2 (Билли)", "pyttsx3", "Выкл."])
        voice_cb.setStyleSheet(
            "QComboBox{background:#1a1a2e;color:#e8e8f0;border:1px solid #2a2a4a;"
            "border-radius:8px;padding:6px 12px;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#1a1a2e;color:#e8e8f0;"
            "selection-background-color:#ff9e44;}"
        )
        row("Голос:", voice_cb)

        model_cb = QComboBox()
        model_cb.addItems(["qwen2.5:7b", "qwen2.5:3b", "mistral", "llama3.2"])
        model_cb.setStyleSheet(voice_cb.styleSheet())
        row("Модель LLM:", model_cb)

        tts_check = QCheckBox("Включить озвучку")
        tts_check.setChecked(self.tts_enabled)
        tts_check.setStyleSheet("color:#e8e8f0;font-size:13px;")
        row("TTS:", tts_check)

        lay.addStretch()

        ver_lbl = QLabel("Аники v3.1 — Are you ready?")
        ver_lbl.setStyleSheet("color:#444;font-size:11px;")
        ver_lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver_lbl)
        return w

    # ── Приветствие ───────────────────────────────────────────────────────────
    def _welcome(self):
        if self.ai_engine:
            self.add_bot_message("Are you ready? Аники здесь! Чем могу помочь, бро?")
            self._status_bar.set_status("Онлайн", "#50e690")
        else:
            self.add_bot_message(
                "Бро, запусти Ollama — без него я как без мозга!\n\n"
                "1. Скачай: https://ollama.com\n"
                "2. В терминале: ollama run qwen2.5\n"
                "3. Перезапусти меня — Let's go!"
            )
            self._status_bar.set_status("Ollama недоступен", "#ff4444")

        if not self.stt_enabled:
            self.add_bot_message("Микрофон недоступен — пиши текстом, бро! Are you ready?")

    # ── Сообщения ─────────────────────────────────────────────────────────────
    def add_bot_message(self, text: str) -> MessageBubble:
        bubble = MessageBubble(text, is_bot=True)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)
        return bubble

    def add_user_message(self, text: str):
        bubble = MessageBubble(text, is_bot=False)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def show_reminder_notification(self, title: str, message: str):
        self.add_bot_message(f"🔔 **{title}**\n{message}")

    # ── Отправка ──────────────────────────────────────────────────────────────
    def _send_message(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.add_user_message(text)

        if not self.ai_engine:
            self.add_bot_message("ИИ недоступен — запусти Ollama, бро!")
            return

        self._start_ai(text)

    def _start_ai(self, text: str):
        self._typing_label.show()
        self._status_bar.set_status("Думает...", "#ffaa44", blink=True)
        self.avatar_thinking.emit(True)
        self._btn_send.setEnabled(False)

        self._current_bubble = None

        self._ai_thread = QThread(self)
        self._worker    = AIWorker(self.ai_engine, text)
        self._worker.moveToThread(self._ai_thread)

        self._ai_thread.started.connect(self._worker.run)
        self._worker.token_ready.connect(self._on_token)
        self._worker.response_ready.connect(self._on_response)
        self._worker.finished.connect(self._on_ai_done)
        self._worker.error.connect(lambda e: self.add_bot_message(f"Ошибка: {e}"))

        self._ai_thread.start()

    def _on_token(self, token: str):
        if self._current_bubble is None:
            self._typing_label.hide()
            self._current_bubble = self.add_bot_message("")
            self.avatar_thinking.emit(False)
            self.avatar_speaking.emit(True)
        self._current_bubble.append_text(token)
        self._scroll_to_bottom()

    def _on_response(self, full_text: str):
        if self.tts_enabled:
            import threading
            from core.tts import speak
            threading.Thread(target=speak, args=(full_text,), daemon=True).start()

    def _on_ai_done(self):
        self._typing_label.hide()
        self._status_bar.set_status("Онлайн", "#50e690")
        self.avatar_thinking.emit(False)
        self.avatar_speaking.emit(False)
        self._btn_send.setEnabled(True)
        self._current_bubble = None
        if self._ai_thread:
            self._ai_thread.quit()
            self._ai_thread.wait()

    # ── Микрофон ──────────────────────────────────────────────────────────────
    def _toggle_mic(self, on: bool):
        self._mic_active = on
        self.avatar_listening.emit(on)
        if on:
            self._status_bar.set_status("Слушаю...", "#c060ff", blink=True)
        else:
            self._status_bar.set_status("Онлайн", "#50e690")

    def on_voice_input(self, text: str):
        if text.strip():
            self._input.setPlainText(text)
            self._send_message()

    # ── Клавиши ───────────────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return True
        return super().eventFilter(obj, event)
