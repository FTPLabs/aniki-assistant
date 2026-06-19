"""
  Система напоминаний Аники v2.2.
  FIX [H1]: убран импорт несуществующей get_gaming_session_duration.
  FIX [H2]: исправлен отступ _check_gaming_session (6 пробелов → 4).
  """

  import threading
  import time
  import logging
  from datetime import datetime, timedelta
  from typing import Callable, Optional, List, Dict

  from .memory import (
      get_active_reminders,
      update_reminder_triggered,
      add_reminder as db_add_reminder,
      deactivate_reminder,
  )
  from .personality import get_phrase

  logger = logging.getLogger(__name__)


  class ReminderSystem:

      def __init__(self, on_reminder: Callable[[str, str], None], check_interval: int = 30):
          self.on_reminder    = on_reminder
          self.check_interval = check_interval
          self._running       = False
          self._thread: Optional[threading.Thread] = None
          self._gaming_session_start: Optional[datetime] = None
          self._gaming_reminder_sent_at: Optional[datetime] = None
          self._water_interval_min  = 60
          self._break_interval_min  = 90
          self._gaming_alert_after_min = 120

      def start(self):
          self._running = True
          self._thread  = threading.Thread(target=self._check_loop, daemon=True)
          self._thread.start()
          logger.info("Система напоминаний запущена")

      def stop(self):
          self._running = False
          if self._thread:
              self._thread.join(timeout=5)

      def notify_gaming_started(self):
          self._gaming_session_start    = datetime.now()
          self._gaming_reminder_sent_at = None

      def notify_gaming_ended(self):
          self._gaming_session_start = None

      def _check_loop(self):
          while self._running:
              try:
                  self._check_db_reminders()
                  self._check_gaming_session()
              except Exception as e:
                  logger.error(f"Ошибка напоминаний: {e}")
              time.sleep(self.check_interval)

      def _check_gaming_session(self):
          """Предупреждение о длинной игровой сессии."""
          if not self._gaming_session_start:
              return
          elapsed_min = (datetime.now() - self._gaming_session_start).total_seconds() / 60
          if elapsed_min < self._gaming_alert_after_min:
              return
          if self._gaming_reminder_sent_at:
              since_last = (datetime.now() - self._gaming_reminder_sent_at).total_seconds() / 60
              if since_last < 30:
                  return
          self._gaming_reminder_sent_at = datetime.now()
          hrs  = int(elapsed_min // 60)
          mins = int(elapsed_min % 60)
          t    = f"{hrs}ч {mins}мин" if hrs else f"{int(elapsed_min)}мин"
          self.on_reminder(
              "Игровой перерыв!",
              f"Бро, ты уже {t} за игрой! Встань, разомнись — no pain no gain!"
          )

      def _check_db_reminders(self):
          """
          FIX: Если last_triggered = NULL и reminder без конкретного времени —
          устанавливаем last_triggered = now и пропускаем первый тик.
          """
          now       = datetime.now()
          reminders = get_active_reminders()

          for r in reminders:
              remind_at      = r.get("remind_at")
              repeat_minutes = r.get("repeat_minutes", 0)
              last_triggered = r.get("last_triggered")
              title          = r.get("title", "")
              description    = r.get("description", "")
              rid            = r.get("id")

              if remind_at:
                  try:
                      remind_dt = datetime.fromisoformat(str(remind_at))
                      if now >= remind_dt:
                          if repeat_minutes > 0:
                              if last_triggered:
                                  elapsed = (now - datetime.fromisoformat(str(last_triggered))).total_seconds()
                                  if elapsed >= repeat_minutes * 60:
                                      self._fire(title, description or title, rid)
                              else:
                                  self._fire(title, description or title, rid)
                          else:
                              self._fire(title, description or title, rid)
                              deactivate_reminder(rid)
                  except (ValueError, TypeError):
                      pass

              elif repeat_minutes > 0:
                  if not last_triggered:
                      update_reminder_triggered(rid)
                  else:
                      try:
                          elapsed = (now - datetime.fromisoformat(str(last_triggered))).total_seconds()
                          if elapsed >= repeat_minutes * 60:
                              self._fire(title, description or title, rid)
                      except (ValueError, TypeError):
                          pass

      def _fire(self, title: str, message: str, rid: Optional[int] = None):
          if rid:
              update_reminder_triggered(rid)
          logger.info(f"Напоминание: {title}")
          try:
              self.on_reminder(title, message)
          except Exception as e:
              logger.error(f"Ошибка callback напоминания: {e}")

      def add_reminder(self, title: str, description: str = "",
                       remind_at=None, repeat_minutes: int = 0) -> int:
          """Добавить напоминание. Используется из ChatWindow."""
          rid = db_add_reminder(title, description, remind_at, repeat_minutes)
          logger.info(f"Напоминание #{rid}: {title}")
          return rid

      add = add_reminder

      def get_all_reminders(self) -> List[Dict]:
          return get_active_reminders()

      def set_water_interval(self, minutes: int):
          self._water_interval_min = max(15, minutes)

      def set_break_interval(self, minutes: int):
          self._break_interval_min = max(30, minutes)

      def set_gaming_alert_threshold(self, minutes: int):
          self._gaming_alert_after_min = max(30, minutes)
  