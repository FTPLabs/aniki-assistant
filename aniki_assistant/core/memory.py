"""
Память Аники — SQLite база данных.
Хранит: профиль пользователя, факты, напоминания, историю разговоров.
Поддерживает забывание: forget_last(), forget_about(topic), clear_history().
"""

import sqlite3
import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "aniki_memory.db"
)


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
    conn = get_connection()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    if count == 0:
        defaults = [
            ("Попей воды!", "Не забывай пить воду — важно для здоровья!", None, 60, 1),
            ("Сделай перерыв", "Встань, разомнись, отдохни от экрана.", None, 90, 1),
        ]
        for title, desc, ra, rm, active in defaults:
            cursor.execute(
                "INSERT INTO reminders (title,description,remind_at,repeat_minutes,is_active)"
                " VALUES (?,?,?,?,?)",
                (title, desc, ra, rm, active)
            )
        conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Профиль ───────────────────────────────────────────────────────────────────

def set_profile(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO user_profile (key, value, updated_at) VALUES (?,?,?)",
        (key, value, datetime.now())
    )
    conn.commit()
    conn.close()


def get_profile(key: str) -> Optional[str]:
    conn = get_connection()
    row = conn.execute("SELECT value FROM user_profile WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def get_all_profile() -> Dict[str, str]:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def delete_profile(key: str):
    """Удалить запись из профиля."""
    conn = get_connection()
    conn.execute("DELETE FROM user_profile WHERE key=?", (key,))
    conn.commit()
    conn.close()


# ── Факты ─────────────────────────────────────────────────────────────────────

def add_fact(content: str, category: str = "general"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO facts (content, category) VALUES (?,?)",
        (content, category)
    )
    conn.commit()
    conn.close()


def get_facts(category: Optional[str] = None, limit: int = 20) -> List[str]:
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


def forget_facts_about(topic: str) -> int:
    """Удалить факты содержащие ключевое слово. Возвращает кол-во удалённых."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM facts WHERE LOWER(content) LIKE ?",
        (f"%{topic.lower()}%",)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def clear_all_facts() -> int:
    conn = get_connection()
    cursor = conn.execute("DELETE FROM facts")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


# ── Разговорная история ───────────────────────────────────────────────────────

def add_message(role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversation_history (role, content) VALUES (?,?)",
        (role, content)
    )
    conn.commit()
    conn.close()
    _cleanup_history()


def get_conversation_history(limit: int = 50) -> List[Dict]:
    """Получить последние N сообщений в хронологическом порядке."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM conversation_history "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def forget_last_messages(n: int = 2) -> int:
    """Удалить последние N сообщений из истории."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM conversation_history ORDER BY created_at DESC LIMIT ?",
        (n,)
    ).fetchall()
    ids = [r["id"] for r in rows]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"DELETE FROM conversation_history WHERE id IN ({placeholders})", ids
        )
        conn.commit()
    conn.close()
    return len(ids)


def forget_messages_about(topic: str) -> int:
    """Удалить сообщения содержащие тему."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM conversation_history WHERE LOWER(content) LIKE ?",
        (f"%{topic.lower()}%",)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def clear_conversation_history() -> int:
    """Очистить всю историю разговора."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM conversation_history")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def _cleanup_history(keep: int = 200):
    """Оставить последние N сообщений (большой лимит = полная история)."""
    conn = get_connection()
    conn.execute(
        """DELETE FROM conversation_history WHERE id NOT IN (
            SELECT id FROM conversation_history ORDER BY created_at DESC LIMIT ?
        )""",
        (keep,)
    )
    conn.commit()
    conn.close()


# ── Напоминания ───────────────────────────────────────────────────────────────

def add_reminder(title: str, description: str = "",
                 remind_at: Optional[datetime] = None,
                 repeat_minutes: int = 0) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO reminders (title,description,remind_at,repeat_minutes,is_active)"
        " VALUES (?,?,?,?,1)",
        (title, description, remind_at, repeat_minutes)
    )
    rid = cursor.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_active_reminders() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM reminders WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_reminder_triggered(reminder_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET last_triggered=? WHERE id=?",
        (datetime.now(), reminder_id)
    )
    conn.commit()
    conn.close()


def delete_reminder(reminder_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def deactivate_reminder(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET is_active=0 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


# ── Контекст для ИИ ───────────────────────────────────────────────────────────

def build_context_string() -> str:
    """Создать строку контекста из памяти для ИИ-запроса."""
    profile = get_all_profile()
    facts   = get_facts(limit=15)

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


# ── Активность ────────────────────────────────────────────────────────────────

def log_activity_start(activity_type: str, metadata: Optional[dict] = None) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO activity_log (activity_type, metadata) VALUES (?,?)",
        (activity_type, json.dumps(metadata) if metadata else None)
    )
    aid = cursor.lastrowid
    conn.commit()
    conn.close()
    return aid


def log_activity_end(activity_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE activity_log SET ended_at=? WHERE id=?",
        (datetime.now(), activity_id)
    )
    conn.commit()
    conn.close()


def get_gaming_session_duration() -> Optional[timedelta]:
    conn = get_connection()
    row = conn.execute(
        "SELECT started_at FROM activity_log "
        "WHERE activity_type='gaming' AND ended_at IS NULL "
        "ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        started = datetime.fromisoformat(row["started_at"])
        return datetime.now() - started
    return None
