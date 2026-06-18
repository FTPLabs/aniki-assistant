"""
Система обучения Аники — запоминает что сработало, когда пользователь говорит «Молодец».
"""

import logging
from typing import Optional
from .memory import get_connection, get_profile
from datetime import datetime

logger = logging.getLogger(__name__)

POSITIVE_TRIGGERS = {
    "молодец", "правильно", "верно", "отлично", "супер", "хорошо",
    "да так", "именно", "точно", "правда", "так и есть", "ты прав",
    "well done", "good job", "nice", "correct", "perfect", "yes",
    "огонь", "топ", "красава", "зачёт", "сделал", "класс",
}

NEGATIVE_TRIGGERS = {
    "неправильно", "нет", "не так", "ошибка", "неверно", "плохо",
    "не то", "не угадал", "неточно", "не верно",
}


def init_learning_table():
    """Создать таблицу обученных знаний если нет."""
    conn = get_connection()
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
    conn.close()


def save_last_exchange(user_text: str, bot_text: str):
    """Сохранить последний обмен для обучения."""
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO last_exchange (id, user_text, bot_text, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                user_text=excluded.user_text,
                bot_text=excluded.bot_text,
                updated_at=excluded.updated_at
        """, (user_text, bot_text, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка сохранения обмена: {e}")


def get_last_exchange() -> Optional[tuple[str, str]]:
    """Получить последний обмен."""
    try:
        conn = get_connection()
        row = conn.execute("SELECT user_text, bot_text FROM last_exchange WHERE id=1").fetchone()
        conn.close()
        if row:
            return row["user_text"], row["bot_text"]
    except Exception:
        pass
    return None


def confirm_last_response():
    """Пользователь сказал 'Молодец' — сохраняем пару вопрос→ответ."""
    exchange = get_last_exchange()
    if not exchange:
        return
    user_text, bot_text = exchange
    if not user_text or not bot_text:
        return
    try:
        conn = get_connection()
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
        conn.close()
        logger.info(f"Обучен: '{user_text[:50]}...'")
    except Exception as e:
        logger.error(f"Ошибка обучения: {e}")


def find_learned_response(user_text: str) -> Optional[str]:
    """Поискать выученный ответ на похожий вопрос."""
    try:
        conn = get_connection()
        query_words = set(user_text.lower().split())
        rows = conn.execute(
            "SELECT trigger_text, response_text, score FROM learned_responses ORDER BY score DESC LIMIT 50"
        ).fetchall()
        conn.close()

        best_score = 0
        best_response = None
        for row in rows:
            trigger_words = set(row["trigger_text"].split())
            if not trigger_words:
                continue
            overlap = len(query_words & trigger_words)
            match_ratio = overlap / max(len(trigger_words), 1)
            weighted = match_ratio * row["score"]
            if weighted > best_score and match_ratio > 0.6:
                best_score = weighted
                best_response = row["response_text"]

        return best_response
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return None


def check_feedback(user_text: str) -> Optional[str]:
    """
    Проверяет — это фидбек ('Молодец' / 'Нет') или обычный вопрос.
    Возвращает 'positive', 'negative' или None.
    """
    words = set(user_text.lower().split())
    if words & POSITIVE_TRIGGERS:
        return "positive"
    if words & NEGATIVE_TRIGGERS:
        return "negative"
    return None
