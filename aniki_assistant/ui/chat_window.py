"""
Окно чата Аники v2.2 — стриминг TTS, исправленные напоминания.
FIX: reminder_system.add_reminder() вместо .add().
FIX: StreamTTS — Аники начинает говорить сразу с первого предложения.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
        QLineEdit, QPushButton, QLabel, QScrollArea,
        QFrame, QSizePolicy, QSpacerItem, QApplication,
        QListWidget, QDialog, QDialogButtonBox,
        QTabWidget, QFormLayout, QSpinBox, QDateTimeEdit,
        QCheckBox, QMessageBox,
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime, QObject
    from PyQt6.QtGui import QFont, QColor, QPixmap
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


if PYQT_AVAILABLE:

    class AIWorker(QThread):
        response_chunk  = pyqtSignal(str)
        response_done   = pyqtSignal(str)
        thinking_start  = pyqtSignal()
        error           = pyqtSignal(str)
        prompt_ready    = pyqtSignal(str)
        speak_sentence  = pyqtSignal(str)   # NEW: стриминговый TTS

        def __init__(self, ai_engine, message: str, tts_enabled: bool = True):
            super().__init__()
            self.ai_engine   = ai_engine
            self.message     = message
            self.tts_enabled = tts_enabled

        def run(self):
            try:
                self.thinking_start.emit()
                full      = ""
                is_prompt = False
                tts_buf   = ""

                from core.commands import PROMPT_MARKER, is_prompt_result, extract_prompt
                import re
                SENT_END = re.compile(r'([.!?…]+[\s\n]|[.!?…]+$)')

                for chunk in self.ai_engine.chat_stream(self.message):
                    if chunk == PROMPT_MARKER:
                        is_prompt = True
                        continue
                    full    += chunk
                    tts_buf += chunk
                    self.response_chunk.emit(chunk)

                    # Стриминговый TTS: отправляем предложения сразу
                    if self.tts_enabled and not is_prompt:
                        while True:
                            m = SENT_END.search(tts_buf)
                            if not m:
                                break
                            end      = m.end()
                            sentence = tts_buf[:end].strip()
                            tts_buf  = tts_buf[end:]
                            if sentence and len(sentence) > 5:
                                self.speak_sentence.emit(sentence)

                # Остаток буфера TTS
                if self.tts_enabled and not is_prompt and tts_buf.strip():
                    self.speak_sentence.emit(tts_buf.strip())

                if is_prompt or is_prompt_result(full):
                    prompt_text = extract_prompt(full) if is_prompt_result(full) else full
                    self.prompt_ready.emit(prompt_text.strip())
                else:
                    self.response_done.emit(full)

            except Exception as e:
                self.error.emit(str(e))


    class VADThread(QThread):
        text_recognized   = pyqtSignal(str)
        listening_changed = pyqtSignal(bool)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._listener  = None
            self._stop_flag = False

        def run(self):
            try:
                from core.speech import VoiceListener, is_available
                if not is_available():
                    logger.warning("STT недоступен — VAD отключён")
                    return
                self._listener = VoiceListener(
                    callback=lambda t: self.text_recognized.emit(t),
                    wake_word=None,
                    on_listening_change=lambda v: self.listening_changed.emit(v),
                )
                self._listener.start()
                while not self._stop_flag:
                    self.msleep(200)
                self._listener.stop()
            except Exception as e:
                logger.error(f"VAD поток: {e}")

        def stop_listening(self):
            self._stop_flag = True
            if self._listener:
                self._listener.stop()


    class MessageBubble(QFrame):
        def __init__(self, text: str, is_user: bool = False, parent=None):
            super().__init__(parent)
            self.is_user = is_user
            self._lbl: Optional[QLabel] = None
            self._setup_ui(text)

        def _setup_ui(self, text: str):
            outer = QHBoxLayout(self)
            outer.setContentsMargins(8, 4, 8, 4)
            bubble = QFrame()
            bubble.setMaximumWidth(560)
            bl = QVBoxLayout(bubble)
            bl.setContentsMargins(13, 9, 13, 9)
            bl.setSpacing(3)
            sender = QLabel("Ты" if self.is_user else "Аники")
            sf = QFont("Segoe UI", 8); sf.setBold(True)
            sender.setFont(sf)
            self._lbl = QLabel(text)
            self._lbl.setWordWrap(True)
            self._lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._lbl.setFont(QFont("Segoe UI", 11))
            time_lbl = QLabel(datetime.now().strftime("%H:%M"))
            time_lbl.setFont(QFont("Segoe UI", 7))
            bl.addWidget(sender)
            bl.addWidget(self._lbl)
            bl.addWidget(time_lbl)
            if self.is_user:
                sender.setStyleSheet("color:#a0c4ff;")
                time_lbl.setStyleSheet("color:#a0c4ff;")
                bubble.setStyleSheet("QFrame{background:#1a4a8a;border-radius:14px;border-bottom-right-radius:3px;}")
                outer.addSpacerItem(QSpacerItem(40,0,QSizePolicy.Policy.Expanding))
                outer.addWidget(bubble)
            else:
                sender.setStyleSheet("color:#ff9e44;")
                time_lbl.setStyleSheet("color:#666;")
                bubble.setStyleSheet("QFrame{background:#1e1e32;border-radius:14px;border-bottom-left-radius:3px;}")
                outer.addWidget(bubble)
                outer.addSpacerItem(QSpacerItem(40,0,QSizePolicy.Policy.Expanding))

        def update_text(self, text: str):
            if self._lbl:
                self._lbl.setText(text)


    class PromptDialog(QDialog):
        def __init__(self, prompt_text: str, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Аники написал промпт")
            self.setMinimumSize(640, 420)
            self.setStyleSheet("QDialog{background:#0d0d1e;color:white;}")
            layout = QVBoxLayout(self)
            lbl = QLabel("Готовый промпт — скопируй и используй:")
            lbl.setStyleSheet("color:#ff9e44;font-size:13px;font-weight:bold;")
            layout.addWidget(lbl)
            self._editor = QTextEdit()
            self._editor.setPlainText(prompt_text)
            self._editor.setStyleSheet(
                "QTextEdit{background:#12122a;color:white;border:1px solid #3a3a5e;"
                "border-radius:8px;padding:10px;font-size:13px;font-family:'Segoe UI';}"
            )
            layout.addWidget(self._editor)
            btn_row = QHBoxLayout()
            copy_btn = QPushButton("📋 Скопировать")
            copy_btn.setStyleSheet(
                "QPushButton{background:#ff9e44;color:#1a1a2e;border-radius:7px;"
                "padding:9px 20px;font-weight:bold;}QPushButton:hover{background:#ffb344;}"
            )
            copy_btn.clicked.connect(lambda: (
                QApplication.clipboard().setText(self._editor.toPlainText()),
                QMessageBox.information(self, "Скопировано!", "Промпт в буфере!")
            ))
            close_btn = QPushButton("Закрыть")
            close_btn.setStyleSheet(
                "QPushButton{background:#1e1e32;color:white;border-radius:7px;"
                "padding:9px 16px;border:1px solid #3a3a5e;}QPushButton:hover{background:#2a2a4e;}"
            )
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(copy_btn)
            btn_row.addWidget(close_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)


    class ReminderDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Новое напоминание")
            self.setMinimumWidth(400)
            self.setStyleSheet("QDialog{background:#0d0d1e;color:white;}")
            layout = QVBoxLayout(self)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            self.title_input = QLineEdit()
            self.title_input.setPlaceholderText("Название")
            self.title_input.setStyleSheet(_inp())
            form.addRow("Название:", self.title_input)
            self.desc_input = QTextEdit()
            self.desc_input.setPlaceholderText("Описание (необязательно)")
            self.desc_input.setMaximumHeight(70)
            self.desc_input.setStyleSheet(_inp())
            form.addRow("Описание:", self.desc_input)
            self.repeat_check = QCheckBox("Повторять каждые")
            self.repeat_check.setStyleSheet("color:white;")
            self.repeat_spin = QSpinBox()
            self.repeat_spin.setRange(1, 1440)
            self.repeat_spin.setValue(60)
            self.repeat_spin.setSuffix(" мин")
            self.repeat_spin.setStyleSheet("color:white;background:#1e1e32;padding:5px;")
            rr = QHBoxLayout()
            rr.addWidget(self.repeat_check)
            rr.addWidget(self.repeat_spin)
            form.addRow("Повтор:", rr)
            self.dt_check = QCheckBox("В конкретное время")
            self.dt_check.setStyleSheet("color:white;")
            self.dt_edit = QDateTimeEdit(QDateTime.currentDateTime())
            self.dt_edit.setEnabled(False)
            self.dt_check.toggled.connect(self.dt_edit.setEnabled)
            form.addRow("Время:", self.dt_check)
            form.addRow("", self.dt_edit)
            layout.addLayout(form)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)
            layout.addWidget(btns)

        def get_data(self) -> dict:
            return {
                "title":          self.title_input.text(),
                "description":    self.desc_input.toPlainText(),
                "remind_at":      self.dt_edit.dateTime().toPyDateTime() if self.dt_check.isChecked() else None,
                "repeat_minutes": self.repeat_spin.value() if self.repeat_check.isChecked() else 0,
            }


    def _inp() -> str:
        return ("background:#1e1e32;color:white;border:1px solid #3a3a5e;"
                "border-radius:6px;padding:6px;font-size:12px;")


    class ChatWindow(QWidget):
        message_sent     = pyqtSignal(str)
        avatar_thinking  = pyqtSignal(bool)
        avatar_speaking  = pyqtSignal(bool)
        avatar_listening = pyqtSignal(bool)

        def __init__(self, ai_engine=None, reminder_system=None,
                     tts_enabled: bool = True, stt_enabled: bool = True):
            super().__init__()
            self.ai_engine        = ai_engine
            self.reminder_system  = reminder_system
            self.tts_enabled      = tts_enabled
            self.stt_enabled      = stt_enabled
            self._current_bubble: Optional[MessageBubble] = None
            self._current_text    = ""
            self._worker: Optional[AIWorker] = None
            self._vad_thread: Optional[VADThread] = None
            self._tts_speaking    = False
            self._setup_ui()
            self._apply_dark_theme()
            if self.stt_enabled:
                QTimer.singleShot(2000, self._start_vad)

        def _setup_ui(self):
            self.setWindowTitle("Аники — ИИ-ассистент")
            self.setMinimumSize(700, 740)
            self.resize(780, 840)
            ml = QVBoxLayout(self)
            ml.setContentsMargins(0, 0, 0, 0)
            ml.setSpacing(0)
            ml.addWidget(self._build_header())
            self.tabs = self._build_tabs()
            ml.addWidget(self.tabs)
            self._add_welcome_message()

        def _build_header(self) -> QFrame:
            h = QFrame()
            h.setFixedHeight(60)
            h.setStyleSheet("background:#12122a;border-bottom:1px solid #2a2a4e;")
            lay = QHBoxLayout(h)
            title = QLabel("  АНИКИ")
            f = QFont("Segoe UI", 17); f.setBold(True)
            title.setFont(f)
            title.setStyleSheet("color:#ff9e44;letter-spacing:2px;")
            self.status_label = QLabel("● Онлайн")
            self.status_label.setStyleSheet("color:#44ff88;font-size:11px;")
            self.vad_label = QLabel()
            self.vad_label.setStyleSheet("color:#44aaff;font-size:11px;")
            lay.addWidget(title)
            lay.addStretch()
            lay.addWidget(self.vad_label)
            lay.addSpacing(12)
            lay.addWidget(self.status_label)
            return h

        def _build_tabs(self) -> QTabWidget:
            tabs = QTabWidget()
            tabs.setStyleSheet("""
                QTabWidget::pane{border:none;}
                QTabBar::tab{background:#12122a;color:#666;padding:9px 18px;border:none;font-family:'Segoe UI';font-size:12px;}
                QTabBar::tab:selected{background:#0d0d1e;color:#ff9e44;border-bottom:2px solid #ff9e44;}
                QTabBar::tab:hover{color:#ccc;}
            """)
            tabs.addTab(self._create_chat_tab(),      "  Чат  ")
            tabs.addTab(self._create_reminders_tab(), "  Напоминания  ")
            tabs.addTab(self._create_settings_tab(),  "  Настройки  ")
            return tabs

        def _create_chat_tab(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setStyleSheet("border:none;background:#0d0d1e;")
            self.messages_widget = QWidget()
            self.messages_widget.setStyleSheet("background:#0d0d1e;")
            self.messages_layout = QVBoxLayout(self.messages_widget)
            self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.messages_layout.setSpacing(6)
            self.messages_layout.setContentsMargins(10, 10, 10, 10)
            self.scroll_area.setWidget(self.messages_widget)
            inp_frame = QFrame()
            inp_frame.setStyleSheet("QFrame{background:#12122a;border-top:1px solid #2a2a4e;}")
            inp_frame.setFixedHeight(76)
            inp_lay = QHBoxLayout(inp_frame)
            inp_lay.setContentsMargins(14, 12, 14, 12)
            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("Напиши Аники или говори в микрофон...")
            self.input_field.setStyleSheet(
                "QLineEdit{background:#1e1e32;border:1px solid #3a3a5e;border-radius:22px;"
                "padding:10px 18px;color:white;font-size:13px;font-family:'Segoe UI';}"
                "QLineEdit:focus{border:1px solid #ff9e44;}"
            )
            self.input_field.returnPressed.connect(self._send_message)
            self.send_btn = QPushButton("▶")
            self.send_btn.setFixedSize(46, 46)
            self.send_btn.setStyleSheet(
                "QPushButton{background:#ff9e44;border-radius:23px;color:#1a1a2e;font-size:17px;font-weight:bold;}"
                "QPushButton:hover{background:#ffb344;}QPushButton:pressed{background:#e08e34;}"
                "QPushButton:disabled{background:#333;color:#666;}"
            )
            self.send_btn.clicked.connect(self._send_message)
            self.mic_btn = QPushButton("🎤")
            self.mic_btn.setFixedSize(46, 46)
            self.mic_btn.setCheckable(True)
            self.mic_btn.setStyleSheet(
                "QPushButton{background:#1e1e32;border-radius:23px;font-size:17px;border:1px solid #3a3a5e;}"
                "QPushButton:checked{background:#aa2233;border:1px solid #cc2244;}"
                "QPushButton:hover{background:#2a2a4e;}"
            )
            self.mic_btn.toggled.connect(self._toggle_vad)
            inp_lay.addWidget(self.input_field)
            inp_lay.addWidget(self.mic_btn)
            inp_lay.addWidget(self.send_btn)
            lay.addWidget(self.scroll_area)
            lay.addWidget(inp_frame)
            return w

        def _create_reminders_tab(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(14, 14, 14, 14)
            btn_lay = QHBoxLayout()
            add_btn = QPushButton("+ Напоминание")
            add_btn.setStyleSheet(self._btn_primary())
            add_btn.clicked.connect(self._add_reminder_dialog)
            ref_btn = QPushButton("Обновить")
            ref_btn.setStyleSheet(self._btn_secondary())
            ref_btn.clicked.connect(self._refresh_reminders)
            btn_lay.addWidget(add_btn)
            btn_lay.addWidget(ref_btn)
            btn_lay.addStretch()
            self.reminders_list = QListWidget()
            self.reminders_list.setStyleSheet(
                "QListWidget{background:#12122a;border:1px solid #2a2a4e;border-radius:8px;"
                "color:white;font-size:12px;}"
                "QListWidget::item{padding:10px;border-bottom:1px solid #2a2a4e;}"
                "QListWidget::item:selected{background:#2a2a4e;}"
            )
            lay.addLayout(btn_lay)
            lay.addWidget(self.reminders_list)
            self._refresh_reminders()
            return w

        def _create_settings_tab(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(20, 20, 20, 20)
            form = QFormLayout()
            form.setSpacing(14)
            self.tts_check = QCheckBox("Голосовые ответы (TTS)")
            self.tts_check.setChecked(self.tts_enabled)
            self.tts_check.setStyleSheet("color:white;font-size:13px;")
            form.addRow(self.tts_check)
            self.stt_check = QCheckBox("Голосовое управление (VAD)")
            self.stt_check.setChecked(self.stt_enabled)
            self.stt_check.setStyleSheet("color:white;font-size:13px;")
            self.stt_check.toggled.connect(self._toggle_vad)
            form.addRow(self.stt_check)
            self.avatar_check = QCheckBox("Показывать аватар Билли на экране")
            self.avatar_check.setChecked(True)
            self.avatar_check.setStyleSheet("color:white;font-size:13px;")
            form.addRow(self.avatar_check)
            save_btn = QPushButton("Сохранить")
            save_btn.setStyleSheet(self._btn_primary())
            save_btn.clicked.connect(self._save_settings)
            lay.addLayout(form)
            lay.addWidget(save_btn)
            lay.addStretch()
            return w

        def _btn_primary(self) -> str:
            return ("QPushButton{background:#ff9e44;color:#1a1a2e;border-radius:7px;"
                    "padding:9px 20px;font-weight:bold;font-size:13px;}"
                    "QPushButton:hover{background:#ffb344;}"
                    "QPushButton:pressed{background:#e08e34;}")

        def _btn_secondary(self) -> str:
            return ("QPushButton{background:#1e1e32;color:white;border-radius:7px;"
                    "padding:9px 16px;border:1px solid #3a3a5e;font-size:12px;}"
                    "QPushButton:hover{background:#2a2a4e;}")

        def _apply_dark_theme(self):
            self.setStyleSheet("""
                QWidget{background:#0d0d1e;color:white;font-family:'Segoe UI';}
                QTabWidget{background:#0d0d1e;}
                QScrollBar:vertical{background:#12122a;width:7px;border-radius:3px;}
                QScrollBar::handle:vertical{background:#3a3a5e;border-radius:3px;}
                QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
                QLabel{color:white;}
            """)

        def _add_welcome_message(self):
            from core.personality import get_phrase
            self.add_bot_message(get_phrase("greeting"))

        def add_user_message(self, text: str):
            b = MessageBubble(text, is_user=True)
            self.messages_layout.addWidget(b)
            self._scroll_to_bottom()

        def add_bot_message(self, text: str):
            b = MessageBubble(text, is_user=False)
            self.messages_layout.addWidget(b)
            self._scroll_to_bottom()

        def start_streaming_bot_message(self):
            self._current_text   = ""
            self._current_bubble = MessageBubble("...", is_user=False)
            self.messages_layout.addWidget(self._current_bubble)
            self._scroll_to_bottom()

        def append_stream_token(self, token: str):
            from core.commands import PROMPT_MARKER
            if token == PROMPT_MARKER:
                return
            self._current_text += token
            if self._current_bubble:
                self._current_bubble.update_text(self._current_text)
            self._scroll_to_bottom()

        def show_reminder_notification(self, title: str, msg: str):
            self.add_bot_message(f"⏰ {title}\n{msg}")

        def _send_message(self):
            text = self.input_field.text().strip()
            if not text:
                return
            self.input_field.clear()
            self.input_field.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.add_user_message(text)
            self.message_sent.emit(text)
            self._dispatch_to_ai(text)

        def _dispatch_to_ai(self, text: str):
            if self.ai_engine:
                self.start_streaming_bot_message()
                self._worker = AIWorker(self.ai_engine, text, tts_enabled=self.tts_enabled)
                self._worker.thinking_start.connect(lambda: self.avatar_thinking.emit(True))
                self._worker.response_chunk.connect(self.append_stream_token)
                self._worker.response_done.connect(self._on_done)
                self._worker.error.connect(self._on_error)
                self._worker.prompt_ready.connect(self._show_prompt_dialog)
                # FIX: стриминговый TTS — говорит сразу
                self._worker.speak_sentence.connect(self._speak_sentence_async)
                self._worker.start()
            else:
                self.add_bot_message(
                    "Бро, ИИ не инициализирован. Проверь Ollama!\n"
                    "Установи: https://ollama.com и запусти: ollama run mistral"
                )
                self._reset_input()

        def _speak_sentence_async(self, sentence: str):
            """Воспроизводит предложение в фоне (стриминг TTS)."""
            self.avatar_speaking.emit(True)
            from core.tts import _do_speak, _preprocess_text
            def _do():
                _do_speak(_preprocess_text(sentence))
            threading.Thread(target=_do, daemon=True).start()

        def _on_done(self, full_text: str):
            self.avatar_thinking.emit(False)
            QTimer.singleShot(500, lambda: self.avatar_speaking.emit(False))
            self._reset_input()

        def _on_error(self, err: str):
            self.avatar_thinking.emit(False)
            self.avatar_speaking.emit(False)
            self.add_bot_message(f"Ошибка: {err}")
            self._reset_input()

        def _show_prompt_dialog(self, prompt_text: str):
            self.avatar_thinking.emit(False)
            self._reset_input()
            if self._current_bubble:
                self._current_bubble.update_text("Готово! Промпт написан.")
            PromptDialog(prompt_text, self).exec()

        def _reset_input(self):
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_field.setFocus()

        def _scroll_to_bottom(self):
            QTimer.singleShot(60, lambda: (
                self.scroll_area.verticalScrollBar().setValue(
                    self.scroll_area.verticalScrollBar().maximum()
                )
            ))

        def _start_vad(self):
            if self._vad_thread and self._vad_thread.isRunning():
                return
            self._vad_thread = VADThread(self)
            self._vad_thread.text_recognized.connect(self._on_voice_text)
            self._vad_thread.listening_changed.connect(self._on_vad_listening)
            self._vad_thread.start()
            self.mic_btn.setChecked(True)

        def _stop_vad(self):
            if self._vad_thread:
                self._vad_thread.stop_listening()
                self._vad_thread = None
            self.mic_btn.setChecked(False)
            self.vad_label.setText("")
            self.avatar_listening.emit(False)

        def _toggle_vad(self, enabled: bool):
            if enabled:
                self._start_vad()
            else:
                self._stop_vad()

        def _on_voice_text(self, text: str):
            if not text:
                return
            self.input_field.setText(text)
            self.add_user_message(text)
            self.message_sent.emit(text)
            self.input_field.clear()
            self.input_field.setEnabled(False)
            self.send_btn.setEnabled(False)
            self._dispatch_to_ai(text)

        def _on_vad_listening(self, is_active: bool):
            self.avatar_listening.emit(is_active)
            self.vad_label.setText("🎙 Записываю..." if is_active else "")

        def _add_reminder_dialog(self):
            dlg = ReminderDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                data = dlg.get_data()
                if data["title"] and self.reminder_system:
                    # FIX: было .add(), теперь .add_reminder()
                    self.reminder_system.add_reminder(
                        title=data["title"],
                        description=data["description"],
                        remind_at=data["remind_at"],
                        repeat_minutes=data["repeat_minutes"],
                    )
                    self._refresh_reminders()

        def _refresh_reminders(self):
            from core.memory import get_active_reminders
            self.reminders_list.clear()
            for r in get_active_reminders():
                self.reminders_list.addItem(
                    f"⏰ {r['title']} — каждые {r['repeat_minutes']} мин"
                    if r["repeat_minutes"] else f"⏰ {r['title']}"
                )

        def _save_settings(self):
            self.tts_enabled = self.tts_check.isChecked()
            self.stt_enabled = self.stt_check.isChecked()
            if self.stt_enabled:
                self._start_vad()
            else:
                self._stop_vad()
            self.add_bot_message("Настройки сохранены! Are you ready?")
