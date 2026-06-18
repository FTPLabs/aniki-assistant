"""
Память Аники — SQLite база данных.
Хранит: профиль пользователя, факты, напоминания, историю разговоров.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aniki_memory.db")


def init_db():
    """Инициализировать базу данных."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            remind_at TIMESTAMP,
            repeat_minutes INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            last_triggered TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            metadata TEXT
        );
    """)

    conn.commit()
    conn.close()

    _seed_default_reminders()


def _seed_default_reminders():
    """Добавить стандартные напоминания если их нет."""
    conn = get_connection()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    if count == 0:
        now = datetime.now()
        default_reminders = [
            ("Попей воды! 💧", "Не забывай пить воду — это важно для здоровья!", None, 60, 1),
            ("Сделай перерыв 🧍", "Встань, разомнись, отдохни от экрана.", None, 90, 1),
        ]
        for title, desc, remind_at, repeat_min, active in default_reminders:
            cursor.execute(
                "INSERT INTO reminders (title, description, remind_at, repeat_minutes, is_active) VALUES (?,?,?,?,?)",
                (title, desc, remind_at, repeat_min, active)
            )
        conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def set_profile(key: str, value: str):
    """Установить значение в профиле пользователя."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, datetime.now())
    )
    conn.commit()
    conn.close()


def get_profile(key: str) -> Optional[str]:
    """Получить значение из профиля."""
    conn = get_connection()
    row = conn.execute("SELECT value FROM user_profile WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def get_all_profile() -> Dict[str, str]:
    """Получить весь профиль пользователя."""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def add_fact(content: str, category: str = "general"):
    """Запомнить факт о пользователе."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO facts (content, category) VALUES (?, ?)",
        (content, category)
    )
    conn.commit()
    conn.close()


def get_facts(category: Optional[str] = None, limit: int = 20) -> List[str]:
    """Получить факты."""
    conn = get_connection()
    if category:
        rows = conn.execute(
            "SELECT content FROM facts WHERE category=? ORDER BY created_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT content FROM facts ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [r["content"] for r in rows]


def add_reminder(title: str, description: str = "", remind_at: Optional[datetime] = None,
                  repeat_minutes: int = 0) -> int:
    """Добавить напоминание."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO reminders (title, description, remind_at, repeat_minutes, is_active) VALUES (?,?,?,?,1)",
        (title, description, remind_at, repeat_minutes)
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reminder_id


def get_active_reminders() -> List[Dict]:
    """Получить все активные напоминания."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE is_active=1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_reminder_triggered(reminder_id: int):
    """Обновить время последнего срабатывания."""
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET last_triggered=? WHERE id=?",
        (datetime.now(), reminder_id)
    )
    conn.commit()
    conn.close()


def delete_reminder(reminder_id: int):
    """Удалить напоминание."""
    conn = get_connection()
    conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def deactivate_reminder(reminder_id: int):
    """Деактивировать напоминание."""
    conn = get_connection()
    conn.execute("UPDATE reminders SET is_active=0 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def add_message(role: str, content: str):
    """Добавить сообщение в историю разговора."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversation_history (role, content) VALUES (?,?)",
        (role, content)
    )
    conn.commit()
    conn.close()
    _cleanup_history()


def get_conversation_history(limit: int = 20) -> List[Dict]:
    """Получить историю разговора."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM conversation_history ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _cleanup_history(keep: int = 100):
    """Оставить только последние N сообщений."""
    conn = get_connection()
    conn.execute(
        """DELETE FROM conversation_history WHERE id NOT IN (
            SELECT id FROM conversation_history ORDER BY created_at DESC LIMIT ?
        )""",
        (keep,)
    )
    conn.commit()
    conn.close()


def log_activity_start(activity_type: str, metadata: Optional[dict] = None) -> int:
    """Начать запись активности."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO activity_log (activity_type, metadata) VALUES (?,?)",
        (activity_type, json.dumps(metadata) if metadata else None)
    )
    activity_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return activity_id


def log_activity_end(activity_id: int):
    """Завершить запись активности."""
    conn = get_connection()
    conn.execute(
        "UPDATE activity_log SET ended_at=? WHERE id=?",
        (datetime.now(), activity_id)
    )
    conn.commit()
    conn.close()


def get_gaming_session_duration() -> Optional[timedelta]:
    """Получить продолжительность текущей игровой сессии."""
    conn = get_connection()
    row = conn.execute(
        "SELECT started_at FROM activity_log WHERE activity_type='gaming' AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        started = datetime.fromisoformat(row["started_at"])
        return datetime.now() - started
    return None


def build_context_string() -> str:
    """Создать строку контекста для ИИ из памяти."""
    profile = get_all_profile()
    facts = get_facts(limit=10)

    lines = []
    if profile:
        lines.append("ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:")
        for k, v in profile.items():
            lines.append(f"  - {k}: {v}")

    if facts:
        lines.append("\nЗАПОМНЕНЫЕ ФАКТЫ:")
        for f in facts:
            lines.append(f"  - {f}")

    return "\n".join(lines) if lines else ""
