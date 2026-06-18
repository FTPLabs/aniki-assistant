"""
Память Аники — SQLite база данных (потокобезопасная версия).
"""

import sqlite3
import json
import os
import threading
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "aniki_memory.db"
)

# Глобальный замок для всех операций с БД
_db_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # WAL — меньше блокировок
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _exec(sql: str, params=(), fetchone=False, fetchall=False, script=False):
    """Потокобезопасное выполнение SQL."""
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            if script:
                cur.executescript(sql)
            else:
                cur.execute(sql, params)
            conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            return cur.rowcount
        finally:
            conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _exec("""
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
    """, script=True)
    _seed_default_reminders()


def _seed_default_reminders():
    with _db_lock:
        conn = get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
            if count == 0:
                defaults = [
                    ("Попей воды!", "Не забывай пить воду!", None, 60, 1),
                    ("Сделай перерыв", "Встань, разомнись!", None, 90, 1),
                ]
                for t, d, ra, rm, a in defaults:
                    conn.execute(
                        "INSERT INTO reminders (title,description,remind_at,repeat_minutes,is_active,last_triggered)"
                        " VALUES (?,?,?,?,?,?)",
                        (t, d, ra, rm, a, datetime.now())  # ← FIX: last_triggered = now
                    )
                conn.commit()
        finally:
            conn.close()


# ── Профиль ──────────────────────────────────────────────────────────────────

def set_profile(key: str, value: str):
    _exec(
        "INSERT OR REPLACE INTO user_profile (key, value, updated_at) VALUES (?,?,?)",
        (key, value, datetime.now())
    )


def get_profile(key: str) -> Optional[str]:
    row = _exec("SELECT value FROM user_profile WHERE key=?", (key,), fetchone=True)
    return row["value"] if row else None


def get_all_profile() -> Dict[str, str]:
    rows = _exec("SELECT key, value FROM user_profile", fetchall=True)
    return {r["key"]: r["value"] for r in rows} if rows else {}


def delete_profile(key: str):
    _exec("DELETE FROM user_profile WHERE key=?", (key,))


# ── Факты ─────────────────────────────────────────────────────────────────────

def add_fact(content: str, category: str = "general"):
    _exec("INSERT INTO facts (content, category) VALUES (?,?)", (content, category))


def get_facts(category: Optional[str] = None, limit: int = 20) -> List[str]:
    if category:
        rows = _exec(
            "SELECT content FROM facts WHERE category=? ORDER BY created_at DESC LIMIT ?",
            (category, limit), fetchall=True
        )
    else:
        rows = _exec(
            "SELECT content FROM facts ORDER BY created_at DESC LIMIT ?",
            (limit,), fetchall=True
        )
    return [r["content"] for r in rows] if rows else []


def forget_facts_about(topic: str) -> int:
    return _exec(
        "DELETE FROM facts WHERE LOWER(content) LIKE ?",
        (f"%{topic.lower()}%",)
    )


def clear_all_facts() -> int:
    return _exec("DELETE FROM facts")


# ── История разговора ────────────────────────────────────────────────────────

def add_message(role: str, content: str):
    _exec(
        "INSERT INTO conversation_history (role, content) VALUES (?,?)",
        (role, content)
    )
    _cleanup_history()


def get_conversation_history(limit: int = 50) -> List[Dict]:
    rows = _exec(
        "SELECT role, content FROM conversation_history ORDER BY created_at DESC LIMIT ?",
        (limit,), fetchall=True
    )
    if not rows:
        return []
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def forget_last_messages(n: int = 2) -> int:
    with _db_lock:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id FROM conversation_history ORDER BY created_at DESC LIMIT ?", (n,)
            ).fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                ph = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM conversation_history WHERE id IN ({ph})", ids)
                conn.commit()
            return len(ids)
        finally:
            conn.close()


def forget_messages_about(topic: str) -> int:
    return _exec(
        "DELETE FROM conversation_history WHERE LOWER(content) LIKE ?",
        (f"%{topic.lower()}%",)
    )


def clear_conversation_history() -> int:
    return _exec("DELETE FROM conversation_history")


def _cleanup_history(keep: int = 200):
    _exec(
        "DELETE FROM conversation_history WHERE id NOT IN "
        "(SELECT id FROM conversation_history ORDER BY created_at DESC LIMIT ?)",
        (keep,)
    )


# ── Напоминания ───────────────────────────────────────────────────────────────

def add_reminder(title: str, description: str = "",
                 remind_at: Optional[datetime] = None,
                 repeat_minutes: int = 0) -> int:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO reminders (title,description,remind_at,repeat_minutes,is_active,last_triggered)"
                " VALUES (?,?,?,?,1,?)",
                (title, description, remind_at, repeat_minutes, datetime.now())
            )
            rid = cur.lastrowid
            conn.commit()
            return rid
        finally:
            conn.close()


def get_active_reminders() -> List[Dict]:
    rows = _exec("SELECT * FROM reminders WHERE is_active=1", fetchall=True)
    return [dict(r) for r in rows] if rows else []


def update_reminder_triggered(reminder_id: int):
    _exec(
        "UPDATE reminders SET last_triggered=? WHERE id=?",
        (datetime.now(), reminder_id)
    )


def delete_reminder(reminder_id: int):
    _exec("DELETE FROM reminders WHERE id=?", (reminder_id,))


def deactivate_reminder(reminder_id: int):
    _exec("UPDATE reminders SET is_active=0 WHERE id=?", (reminder_id,))


# ── Контекст для ИИ ───────────────────────────────────────────────────────────

def build_context_string() -> str:
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
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO activity_log (activity_type, metadata) VALUES (?,?)",
                (activity_type, json.dumps(metadata) if metadata else None)
            )
            aid = cur.lastrowid
            conn.commit()
            return aid
        finally:
            conn.close()


def log_activity_end(activity_id: int):
    _exec(
        "UPDATE activity_log SET ended_at=? WHERE id=?",
        (datetime.now(), activity_id)
    )


def get_gaming_session_duration() -> Optional[timedelta]:
    row = _exec(
        "SELECT started_at FROM activity_log WHERE activity_type='gaming' AND ended_at IS NULL"
        " ORDER BY started_at DESC LIMIT 1",
        fetchone=True
    )
    if row:
        return datetime.now() - datetime.fromisoformat(row["started_at"])
    return None
