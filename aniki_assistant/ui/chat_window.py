"""
Окно чата Аники — PyQt6 интерфейс.
"""

import logging
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
        QLineEdit, QPushButton, QLabel, QScrollArea,
        QFrame, QSizePolicy, QSpacerItem, QApplication,
        QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
        QTabWidget, QFormLayout, QSpinBox, QDateTimeEdit,
        QCheckBox, QMessageBox,
    )
    from PyQt6.QtCore import (
        Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime
    )
    from PyQt6.QtGui import (
        QFont, QColor, QPalette, QTextCursor, QIcon, QPixmap
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger.error("PyQt6 не установлен")


if PYQT_AVAILABLE:
    class AIWorker(QThread):
        """Фоновый поток для запросов к ИИ."""
        response_chunk = pyqtSignal(str)
        response_done = pyqtSignal(str)
        error = pyqtSignal(str)

        def __init__(self, ai_engine, message: str):
            super().__init__()
            self.ai_engine = ai_engine
            self.message = message

        def run(self):
            try:
                full_response = ""
                for chunk in self.ai_engine.chat_stream(self.message):
                    full_response += chunk
                    self.response_chunk.emit(chunk)
                self.response_done.emit(full_response)
            except Exception as e:
                self.error.emit(str(e))


    class MessageBubble(QFrame):
        """Пузырь сообщения в чате."""

        def __init__(self, text: str, is_user: bool = False, parent=None):
            super().__init__(parent)
            self.is_user = is_user
            self._setup_ui(text)

        def _setup_ui(self, text: str):
            layout = QHBoxLayout(self)
            layout.setContentsMargins(8, 4, 8, 4)

            bubble = QFrame()
            bubble.setMaximumWidth(500)

            bubble_layout = QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(12, 8, 12, 8)
            bubble_layout.setSpacing(2)

            sender_label = QLabel("Ты" if self.is_user else "🤜 Аники")
            sender_font = QFont()
            sender_font.setPointSize(8)
            sender_font.setBold(True)
            sender_label.setFont(sender_font)

            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            text_font = QFont()
            text_font.setPointSize(10)
            text_label.setFont(text_font)

            time_label = QLabel(datetime.now().strftime("%H:%M"))
            time_font = QFont()
            time_font.setPointSize(7)
            time_label.setFont(time_font)

            bubble_layout.addWidget(sender_label)
            bubble_layout.addWidget(text_label)
            bubble_layout.addWidget(time_label)

            if self.is_user:
                sender_label.setStyleSheet("color: #a0c4ff;")
                time_label.setStyleSheet("color: #a0c4ff;")
                bubble.setStyleSheet("""
                    QFrame {
                        background-color: #1a4a8a;
                        border-radius: 12px;
                        border-bottom-right-radius: 3px;
                    }
                """)
                layout.addSpacerItem(QSpacerItem(40, 0, QSizePolicy.Policy.Expanding))
                layout.addWidget(bubble)
            else:
                sender_label.setStyleSheet("color: #ff9e44;")
                time_label.setStyleSheet("color: #888;")
                bubble.setStyleSheet("""
                    QFrame {
                        background-color: #2a2a3e;
                        border-radius: 12px;
                        border-bottom-left-radius: 3px;
                    }
                """)
                layout.addWidget(bubble)
                layout.addSpacerItem(QSpacerItem(40, 0, QSizePolicy.Policy.Expanding))


    class ReminderDialog(QDialog):
        """Диалог добавления напоминания."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Новое напоминание")
            self.setMinimumWidth(400)
            self._setup_ui()

        def _setup_ui(self):
            layout = QVBoxLayout(self)

            form = QFormLayout()

            self.title_input = QLineEdit()
            self.title_input.setPlaceholderText("Название напоминания")
            form.addRow("Название:", self.title_input)

            self.desc_input = QTextEdit()
            self.desc_input.setPlaceholderText("Описание (необязательно)")
            self.desc_input.setMaximumHeight(80)
            form.addRow("Описание:", self.desc_input)

            self.repeat_check = QCheckBox("Повторять каждые")
            self.repeat_spin = QSpinBox()
            self.repeat_spin.setRange(1, 1440)
            self.repeat_spin.setValue(60)
            self.repeat_spin.setSuffix(" мин")
            repeat_layout = QHBoxLayout()
            repeat_layout.addWidget(self.repeat_check)
            repeat_layout.addWidget(self.repeat_spin)
            form.addRow("Повтор:", repeat_layout)

            self.datetime_check = QCheckBox("Напомнить в конкретное время")
            self.datetime_edit = QDateTimeEdit(QDateTime.currentDateTime())
            self.datetime_edit.setEnabled(False)
            self.datetime_check.toggled.connect(self.datetime_edit.setEnabled)
            form.addRow("Время:", self.datetime_check)
            form.addRow("", self.datetime_edit)

            layout.addLayout(form)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def get_data(self) -> dict:
            dt = None
            if self.datetime_check.isChecked():
                qdt = self.datetime_edit.dateTime()
                dt = qdt.toPyDateTime()

            return {
                "title": self.title_input.text(),
                "description": self.desc_input.toPlainText(),
                "remind_at": dt,
                "repeat_minutes": self.repeat_spin.value() if self.repeat_check.isChecked() else 0,
            }


    class ChatWindow(QWidget):
        """Главное окно чата."""

        message_sent = pyqtSignal(str)

        def __init__(
            self,
            ai_engine=None,
            reminder_system=None,
            tts_enabled: bool = True,
            stt_enabled: bool = False,
        ):
            super().__init__()
            self.ai_engine = ai_engine
            self.reminder_system = reminder_system
            self.tts_enabled = tts_enabled
            self.stt_enabled = stt_enabled
            self._current_bot_bubble: Optional[MessageBubble] = None
            self._current_bot_text = ""
            self._worker: Optional[AIWorker] = None
            self._setup_ui()
            self._apply_dark_theme()

        def _setup_ui(self):
            self.setWindowTitle("🤜 Аники — ИИ-ассистент")
            self.setMinimumSize(650, 700)
            self.resize(750, 800)

            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            header = QFrame()
            header.setFixedHeight(60)
            header.setStyleSheet("background-color: #1a1a2e; border-bottom: 1px solid #2a2a4e;")
            header_layout = QHBoxLayout(header)

            title_label = QLabel("🤜 АНИКИ")
            title_font = QFont()
            title_font.setPointSize(16)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: #ff9e44;")

            self.status_label = QLabel("● Онлайн")
            self.status_label.setStyleSheet("color: #44ff88; font-size: 11px;")

            header_layout.addWidget(title_label)
            header_layout.addStretch()
            header_layout.addWidget(self.status_label)

            self.tabs = QTabWidget()
            self.tabs.setStyleSheet("""
                QTabWidget::pane { border: none; }
                QTabBar::tab { 
                    background: #1a1a2e; color: #888; 
                    padding: 8px 16px; border: none;
                }
                QTabBar::tab:selected { 
                    background: #0d0d1e; color: #ff9e44; 
                    border-bottom: 2px solid #ff9e44;
                }
            """)

            chat_widget = self._create_chat_tab()
            reminders_widget = self._create_reminders_tab()
            settings_widget = self._create_settings_tab()

            self.tabs.addTab(chat_widget, "💬 Чат")
            self.tabs.addTab(reminders_widget, "⏰ Напоминания")
            self.tabs.addTab(settings_widget, "⚙️ Настройки")

            main_layout.addWidget(header)
            main_layout.addWidget(self.tabs)

            self._add_welcome_message()

        def _create_chat_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setStyleSheet("border: none; background-color: #0d0d1e;")

            self.messages_widget = QWidget()
            self.messages_widget.setStyleSheet("background-color: #0d0d1e;")
            self.messages_layout = QVBoxLayout(self.messages_widget)
            self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.messages_layout.setSpacing(4)
            self.messages_layout.setContentsMargins(8, 8, 8, 8)

            self.scroll_area.setWidget(self.messages_widget)

            input_frame = QFrame()
            input_frame.setStyleSheet("""
                QFrame { 
                    background-color: #1a1a2e; 
                    border-top: 1px solid #2a2a4e;
                }
            """)
            input_frame.setFixedHeight(70)
            input_layout = QHBoxLayout(input_frame)
            input_layout.setContentsMargins(12, 10, 12, 10)

            self.input_field = QLineEdit()
            self.input_field.setPlaceholderText("Напиши Аники что-нибудь...")
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #2a2a3e;
                    border: 1px solid #3a3a5e;
                    border-radius: 20px;
                    padding: 8px 16px;
                    color: white;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #ff9e44;
                }
            """)
            self.input_field.returnPressed.connect(self._send_message)

            self.send_button = QPushButton("▶")
            self.send_button.setFixedSize(44, 44)
            self.send_button.setStyleSheet("""
                QPushButton {
                    background-color: #ff9e44;
                    border-radius: 22px;
                    color: #1a1a2e;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #ffb344; }
                QPushButton:pressed { background-color: #e08e34; }
                QPushButton:disabled { background-color: #444; color: #888; }
            """)
            self.send_button.clicked.connect(self._send_message)

            self.mic_button = QPushButton("🎤")
            self.mic_button.setFixedSize(44, 44)
            self.mic_button.setCheckable(True)
            self.mic_button.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a3e;
                    border-radius: 22px;
                    font-size: 16px;
                    border: 1px solid #3a3a5e;
                }
                QPushButton:checked {
                    background-color: #cc2244;
                    border: 1px solid #ee2244;
                }
                QPushButton:hover { background-color: #3a3a5e; }
            """)

            input_layout.addWidget(self.input_field)
            input_layout.addWidget(self.mic_button)
            input_layout.addWidget(self.send_button)

            layout.addWidget(self.scroll_area)
            layout.addWidget(input_frame)

            return widget

        def _create_reminders_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(12, 12, 12, 12)

            btn_layout = QHBoxLayout()
            add_btn = QPushButton("+ Добавить напоминание")
            add_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff9e44;
                    color: #1a1a2e;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #ffb344; }
            """)
            add_btn.clicked.connect(self._add_reminder_dialog)

            refresh_btn = QPushButton("🔄 Обновить")
            refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a3e;
                    color: white;
                    border-radius: 6px;
                    padding: 8px 16px;
                    border: 1px solid #3a3a5e;
                }
                QPushButton:hover { background-color: #3a3a5e; }
            """)
            refresh_btn.clicked.connect(self._refresh_reminders)

            btn_layout.addWidget(add_btn)
            btn_layout.addWidget(refresh_btn)
            btn_layout.addStretch()

            self.reminders_list = QListWidget()
            self.reminders_list.setStyleSheet("""
                QListWidget {
                    background-color: #1a1a2e;
                    border: 1px solid #2a2a4e;
                    border-radius: 8px;
                    color: white;
                    font-size: 12px;
                }
                QListWidget::item {
                    padding: 10px;
                    border-bottom: 1px solid #2a2a4e;
                }
                QListWidget::item:selected {
                    background-color: #2a2a4e;
                }
            """)

            layout.addLayout(btn_layout)
            layout.addWidget(self.reminders_list)

            self._refresh_reminders()
            return widget

        def _create_settings_tab(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(16, 16, 16, 16)

            form = QFormLayout()
            form.setSpacing(12)

            self.tts_check = QCheckBox("Включить голосовые ответы (TTS)")
            self.tts_check.setChecked(self.tts_enabled)
            self.tts_check.setStyleSheet("color: white; font-size: 13px;")
            form.addRow(self.tts_check)

            self.stt_check = QCheckBox("Включить распознавание речи (STT)")
            self.stt_check.setChecked(self.stt_enabled)
            self.stt_check.setStyleSheet("color: white; font-size: 13px;")
            form.addRow(self.stt_check)

            water_label = QLabel("Напоминание о воде (минуты):")
            water_label.setStyleSheet("color: #aaa; font-size: 12px;")
            self.water_spin = QSpinBox()
            self.water_spin.setRange(15, 480)
            self.water_spin.setValue(60)
            self.water_spin.setStyleSheet("color: white; background: #2a2a3e; padding: 4px;")
            form.addRow(water_label, self.water_spin)

            break_label = QLabel("Напоминание о перерыве (минуты):")
            break_label.setStyleSheet("color: #aaa; font-size: 12px;")
            self.break_spin = QSpinBox()
            self.break_spin.setRange(30, 480)
            self.break_spin.setValue(90)
            self.break_spin.setStyleSheet("color: white; background: #2a2a3e; padding: 4px;")
            form.addRow(break_label, self.break_spin)

            gaming_label = QLabel("Предупреждение об игре (минуты):")
            gaming_label.setStyleSheet("color: #aaa; font-size: 12px;")
            self.gaming_spin = QSpinBox()
            self.gaming_spin.setRange(30, 480)
            self.gaming_spin.setValue(120)
            self.gaming_spin.setStyleSheet("color: white; background: #2a2a3e; padding: 4px;")
            form.addRow(gaming_label, self.gaming_spin)

            save_btn = QPushButton("Сохранить настройки")
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff9e44;
                    color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #ffb344; }
            """)
            save_btn.clicked.connect(self._save_settings)

            layout.addLayout(form)
            layout.addWidget(save_btn)
            layout.addStretch()

            return widget

        def _apply_dark_theme(self):
            self.setStyleSheet("""
                QWidget {
                    background-color: #0d0d1e;
                    color: white;
                    font-family: 'Segoe UI', sans-serif;
                }
                QTabWidget {
                    background-color: #0d0d1e;
                }
                QScrollBar:vertical {
                    background: #1a1a2e;
                    width: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background: #3a3a5e;
                    border-radius: 4px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)

        def _add_welcome_message(self):
            from core.personality import get_phrase
            welcome = get_phrase("greeting")
            self.add_bot_message(welcome)

        def add_user_message(self, text: str):
            bubble = MessageBubble(text, is_user=True)
            self.messages_layout.addWidget(bubble)
            self._scroll_to_bottom()

        def add_bot_message(self, text: str):
            bubble = MessageBubble(text, is_user=False)
            self.messages_layout.addWidget(bubble)
            self._scroll_to_bottom()

        def start_streaming_bot_message(self) -> MessageBubble:
            self._current_bot_text = ""
            self._current_bot_bubble = MessageBubble("...", is_user=False)
            self.messages_layout.addWidget(self._current_bot_bubble)
            self._scroll_to_bottom()
            return self._current_bot_bubble

        def append_stream_token(self, token: str):
            self._current_bot_text += token
            if self._current_bot_bubble:
                for label in self._current_bot_bubble.findChildren(QLabel):
                    if label.text() != "🤜 Аники" and not label.text().startswith("🤜"):
                        try:
                            if ":" not in label.text() or len(label.text()) > 10:
                                label.setText(self._current_bot_text)
                                break
                        except Exception:
                            pass
            self._scroll_to_bottom()

        def _send_message(self):
            text = self.input_field.text().strip()
            if not text:
                return

            self.input_field.clear()
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)

            self.add_user_message(text)
            self.message_sent.emit(text)

            if self.ai_engine:
                self.start_streaming_bot_message()
                self._worker = AIWorker(self.ai_engine, text)
                self._worker.response_chunk.connect(self.append_stream_token)
                self._worker.response_done.connect(self._on_response_done)
                self._worker.error.connect(self._on_response_error)
                self._worker.start()
            else:
                self.add_bot_message("ИИ не инициализирован. Проверь Ollama!")
                self._reset_input()

        def _on_response_done(self, full_text: str):
            self._reset_input()
            if self.tts_enabled and full_text:
                from core.tts import speak
                import threading
                threading.Thread(
                    target=speak,
                    args=(full_text,),
                    kwargs={"blocking": False},
                    daemon=True
                ).start()

        def _on_response_error(self, error: str):
            self.add_bot_message(f"Ошибка: {error}")
            self._reset_input()

        def _reset_input(self):
            self.input_field.setEnabled(True)
            self.send_button.setEnabled(True)
            self.input_field.setFocus()

        def _scroll_to_bottom(self):
            QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ))

        def _add_reminder_dialog(self):
            dialog = ReminderDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                if data["title"] and self.reminder_system:
                    self.reminder_system.add_reminder(
                        title=data["title"],
                        description=data["description"],
                        remind_at=data["remind_at"],
                        repeat_minutes=data["repeat_minutes"],
                    )
                    self._refresh_reminders()
                    self.add_bot_message(f"Let's go! Напоминание «{data['title']}» добавлено!")

        def _refresh_reminders(self):
            self.reminders_list.clear()
            if not self.reminder_system:
                return
            reminders = self.reminder_system.get_all_reminders()
            for r in reminders:
                repeat_info = f" (каждые {r['repeat_minutes']} мин)" if r["repeat_minutes"] else ""
                dt_info = f" в {r['remind_at']}" if r.get("remind_at") else ""
                item_text = f"⏰ {r['title']}{dt_info}{repeat_info}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, r["id"])
                self.reminders_list.addItem(item)

        def _save_settings(self):
            self.tts_enabled = self.tts_check.isChecked()
            self.stt_enabled = self.stt_check.isChecked()
            if self.reminder_system:
                self.reminder_system.set_water_interval(self.water_spin.value())
                self.reminder_system.set_break_interval(self.break_spin.value())
                self.reminder_system.set_gaming_alert_threshold(self.gaming_spin.value())
            self.add_bot_message("I'm your man! Настройки сохранены, чемпион!")

        def show_reminder_notification(self, title: str, message: str):
            """Показать уведомление напоминания в чате."""
            self.add_bot_message(f"⏰ **{title}**\n{message}")
            if self.tts_enabled:
                from core.tts import speak
                import threading
                threading.Thread(target=speak, args=(message,), daemon=True).start()
