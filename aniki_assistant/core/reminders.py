"""
Система напоминаний Аники.
Периодические и одноразовые напоминания с уведомлениями.
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional, List, Dict

from .memory import (
    get_active_reminders,
    update_reminder_triggered,
    get_gaming_session_duration,
    add_reminder as db_add_reminder,
    deactivate_reminder,
)
from .personality import get_phrase

logger = logging.getLogger(__name__)


class ReminderSystem:
    """Система управления напоминаниями."""

    def __init__(
        self,
        on_reminder: Callable[[str, str], None],
        check_interval: int = 30,
    ):
        """
        Args:
            on_reminder: callback(title, message) при срабатывании напоминания
            check_interval: интервал проверки в секундах
        """
        self.on_reminder = on_reminder
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._gaming_session_start: Optional[datetime] = None
        self._last_water_reminder: Optional[datetime] = None
        self._last_break_reminder: Optional[datetime] = None
        self._gaming_reminder_sent_at: Optional[datetime] = None

        self._water_interval_min = 60
        self._break_interval_min = 90
        self._gaming_alert_after_min = 120

    def start(self):
        """Запустить систему напоминаний."""
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Система напоминаний запущена")

    def stop(self):
        """Остановить систему напоминаний."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def notify_gaming_started(self):
        """Уведомить о начале игровой сессии."""
        self._gaming_session_start = datetime.now()
        self._gaming_reminder_sent_at = None
        logger.info("Игровая сессия начата")

    def notify_gaming_ended(self):
        """Уведомить об окончании игровой сессии."""
        self._gaming_session_start = None
        logger.info("Игровая сессия завершена")

    def _check_loop(self):
        """Основной цикл проверки напоминаний."""
        while self._running:
            try:
                self._check_db_reminders()
                self._check_water_reminder()
                self._check_break_reminder()
                self._check_gaming_reminder()
            except Exception as e:
                logger.error(f"Ошибка проверки напоминаний: {e}")

            time.sleep(self.check_interval)

    def _check_db_reminders(self):
        """Проверить напоминания из базы данных."""
        now = datetime.now()
        reminders = get_active_reminders()

        for reminder in reminders:
            remind_at = reminder.get("remind_at")
            repeat_minutes = reminder.get("repeat_minutes", 0)
            last_triggered = reminder.get("last_triggered")
            title = reminder.get("title", "")
            description = reminder.get("description", "")
            reminder_id = reminder.get("id")

            if remind_at:
                try:
                    remind_dt = datetime.fromisoformat(str(remind_at))
                    if now >= remind_dt:
                        if repeat_minutes > 0:
                            if not last_triggered or \
                               (now - datetime.fromisoformat(str(last_triggered))).total_seconds() >= repeat_minutes * 60:
                                self._fire_reminder(title, description or title, reminder_id)
                        else:
                            self._fire_reminder(title, description or title, reminder_id)
                            deactivate_reminder(reminder_id)
                except (ValueError, TypeError):
                    pass

            elif repeat_minutes > 0:
                if not last_triggered:
                    pass
                else:
                    try:
                        last_dt = datetime.fromisoformat(str(last_triggered))
                        if (now - last_dt).total_seconds() >= repeat_minutes * 60:
                            self._fire_reminder(title, description or title, reminder_id)
                    except (ValueError, TypeError):
                        pass

    def _check_water_reminder(self):
        """Напоминание о воде."""
        now = datetime.now()
        if self._last_water_reminder is None:
            self._last_water_reminder = now
            return

        minutes_since = (now - self._last_water_reminder).total_seconds() / 60
        if minutes_since >= self._water_interval_min:
            message = get_phrase("reminder_water")
            self._fire_reminder_direct("💧 Вода!", message)
            self._last_water_reminder = now

    def _check_break_reminder(self):
        """Напоминание о перерыве."""
        now = datetime.now()
        if self._last_break_reminder is None:
            self._last_break_reminder = now
            return

        minutes_since = (now - self._last_break_reminder).total_seconds() / 60
        if minutes_since >= self._break_interval_min:
            message = get_phrase("reminder_break")
            self._fire_reminder_direct("🧍 Перерыв!", message)
            self._last_break_reminder = now

    def _check_gaming_reminder(self):
        """Напоминание об игровом времени."""
        if not self._gaming_session_start:
            return

        now = datetime.now()
        session_minutes = (now - self._gaming_session_start).total_seconds() / 60

        if session_minutes >= self._gaming_alert_after_min:
            if self._gaming_reminder_sent_at is None or \
               (now - self._gaming_reminder_sent_at).total_seconds() >= 30 * 60:
                hours = int(session_minutes // 60)
                mins = int(session_minutes % 60)
                if hours > 0:
                    time_str = f"{hours}ч {mins}мин"
                else:
                    time_str = f"{mins}мин"
                message = get_phrase("reminder_gaming", time=time_str)
                self._fire_reminder_direct("🎮 Пора отдохнуть!", message)
                self._gaming_reminder_sent_at = now

    def _fire_reminder(self, title: str, message: str, reminder_id: Optional[int] = None):
        """Запустить напоминание."""
        if reminder_id:
            update_reminder_triggered(reminder_id)
        self._fire_reminder_direct(title, message)

    def _fire_reminder_direct(self, title: str, message: str):
        """Напрямую вызвать callback напоминания."""
        logger.info(f"Напоминание: {title} — {message}")
        try:
            self.on_reminder(title, message)
        except Exception as e:
            logger.error(f"Ошибка в callback напоминания: {e}")

    def add_reminder(
        self,
        title: str,
        description: str = "",
        remind_at: Optional[datetime] = None,
        repeat_minutes: int = 0,
    ) -> int:
        """Добавить новое напоминание."""
        reminder_id = db_add_reminder(title, description, remind_at, repeat_minutes)
        logger.info(f"Добавлено напоминание #{reminder_id}: {title}")
        return reminder_id

    def get_all_reminders(self) -> List[Dict]:
        """Получить все активные напоминания."""
        return get_active_reminders()

    def set_water_interval(self, minutes: int):
        """Установить интервал напоминания о воде."""
        self._water_interval_min = max(15, minutes)

    def set_break_interval(self, minutes: int):
        """Установить интервал напоминания о перерыве."""
        self._break_interval_min = max(30, minutes)

    def set_gaming_alert_threshold(self, minutes: int):
        """Установить порог игрового времени для предупреждения."""
        self._gaming_alert_after_min = max(30, minutes)
