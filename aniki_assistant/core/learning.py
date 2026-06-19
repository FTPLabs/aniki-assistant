"""
Система обучения Аники — запоминает что сработало.
FIX [C1]: все DB-операции теперь используют _db_lock из memory.py
FIX [H4]: try/finally во всех функциях — нет утечек соединений
"""
import logging
import threading
from typing import Optional
from .memory import get_connection, get_profile, _db_lock
from datetime import datetime

logger = logging.getLogger(__name__)

POSITIVE_TRIGGERS = {
    "молодец", "правильно", "верно", "отлично", "супер", "хорошо",
    "да так", "именно", "точно", "правда", "так и есть", "ты прав",
    "well done", "good job", "nice", "correct", "perfect",
    "огонь", "топ", "красава", "зачёт", "класс",
}

NEGATIVE_TRIGGERS = {
    "неправильно", "неверно", "плохо", "не то", "не угадал", "неточно",
}


def init_learning_table():
    with _db_lock:
        conn = get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trigger_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    score INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS last_exchange (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    user_text TEXT,
                    bot_text TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()


def save_last_exchange(user_text: str, bot_text: str):
    try:
        with _db_lock:
            conn = get_connection()
            try:
                conn.execute("""
                    INSERT INTO last_exchange (id, user_text, bot_text, updated_at)
                    VALUES (1, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        user_text=excluded.user_text,
                        bot_text=excluded.bot_text,
                        updated_at=excluded.updated_at
                """, (user_text, bot_text, datetime.now()))
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"Ошибка сохранения обмена: {e}")


def get_last_exchange() -> Optional[tuple]:
    try:
        with _db_lock:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT user_text, bot_text FROM last_exchange WHERE id=1"
                ).fetchone()
                return (row["user_text"], row["bot_text"]) if row else None
            finally:
                conn.close()
    except Exception:
        return None


def confirm_last_response():
    exchange = get_last_exchange()
    if not exchange:
        return
    user_text, bot_text = exchange
    if not user_text or not bot_text:
        return
    try:
        with _db_lock:
            conn = get_connection()
            try:
                existing = conn.execute(
                    "SELECT id, score FROM learned_responses WHERE trigger_text=?",
                    (user_text.lower().strip(),)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE learned_responses SET score=score+1, last_used=? WHERE id=?",
                        (datetime.now(), existing["id"])
                    )
                else:
                    conn.execute(
                        "INSERT INTO learned_responses (trigger_text, response_text) VALUES (?,?)",
                        (user_text.lower().strip(), bot_text)
                    )
                conn.commit()
            finally:
                conn.close()
        logger.info(f"Обучен: '{user_text[:50]}'")
    except Exception as e:
        logger.error(f"Ошибка обучения: {e}")


def find_learned_response(user_text: str) -> Optional[str]:
    try:
        with _db_lock:
            conn = get_connection()
            try:
                query_words = set(user_text.lower().split())
                rows = conn.execute(
                    "SELECT trigger_text, response_text, score FROM learned_responses ORDER BY score DESC LIMIT 50"
                ).fetchall()
            finally:
                conn.close()
        best_score, best_response = 0.0, None
        for row in rows:
            trigger_words = set(row["trigger_text"].split())
            if not trigger_words:
                continue
            overlap = len(query_words & trigger_words)
            ratio = overlap / max(len(trigger_words), 1)
            weighted = ratio * row["score"]
            if weighted > best_score and ratio > 0.6:
                best_score = weighted
                best_response = row["response_text"]
        return best_response
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return None


def check_feedback(user_text: str) -> Optional[str]:
    """
    FIX: только короткие сообщения (≤4 слова) считаются фидбеком.
    'Нет' в длинном предложении — не отказ.
    """
    words = user_text.strip().split()
    if len(words) > 4:
        return None

    word_set = {w.lower().strip(".,!?") for w in words}
    if word_set & POSITIVE_TRIGGERS:
        return "positive"

    single_negatives = {"нет", "no", "nope", "неверно", "неправильно"}
    if word_set & (NEGATIVE_TRIGGERS | single_negatives):
        return "negative"

    return None
