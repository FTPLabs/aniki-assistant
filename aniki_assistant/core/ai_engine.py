"""
ИИ-движок Аники — интеграция с Ollama + DuckDuckGo + обучение.
"""

import requests
import json
import logging
from typing import Optional, List, Dict, Generator
from .personality import SYSTEM_PROMPT, get_phrase
from .memory import get_conversation_history, add_message, build_context_string, add_fact, set_profile
from .commands import try_parse_command
from .learning import (
    save_last_exchange, find_learned_response,
    confirm_last_response, check_feedback, init_learning_table,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "mistral"
FALLBACK_MODELS = ["mistral", "llama3.2", "llama3.2:3b", "llama3", "llama2", "gemma2", "phi3"]

# Ленивый импорт search чтобы не падать без интернета
_search_available = None


def _try_search(query: str) -> Optional[str]:
    global _search_available
    try:
        from .search import search, is_online
        if _search_available is None:
            _search_available = is_online()
        if _search_available:
            return search(query)
    except Exception as e:
        logger.debug(f"Поиск недоступен: {e}")
    return None


def check_ollama_available() -> bool:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def get_available_models() -> List[str]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def get_best_model() -> str:
    available = get_available_models()
    if not available:
        return DEFAULT_MODEL
    for preferred in FALLBACK_MODELS:
        for model in available:
            if preferred in model.lower():
                return model
    return available[0]


class AnikiAI:
    """Главный ИИ-движок ассистента с поиском и обучением."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self._initialized = False
        init_learning_table()

    def initialize(self) -> bool:
        if not check_ollama_available():
            logger.error("Ollama не запущен!")
            return False
        if not self.model:
            self.model = get_best_model()
            if not self.model:
                logger.error("Нет доступных моделей Ollama")
                return False
        logger.info(f"Используется модель: {self.model}")
        self._initialized = True
        return True

    def _build_messages(self, user_message: str, search_context: str = "") -> List[Dict]:
        context = build_context_string()
        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n{context}"
        if search_context:
            system += f"\n\nНАЙДЕНО В ИНТЕРНЕТЕ (используй если уместно):\n{search_context}"

        messages = [{"role": "system", "content": system}]
        history = get_conversation_history(limit=10)
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def chat(self, user_message: str) -> str:
        if not self._initialized:
            if not self.initialize():
                return "Бро, Ollama не запущен! Установи Ollama и запусти модель."

        # 1. Проверка фидбека пользователя
        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("learned")
            add_message("user", user_message)
            add_message("assistant", reply)
            save_last_exchange(user_message, reply)
            return reply
        elif feedback == "negative":
            reply = "Понял, бро! Запомнил — в следующий раз сделаю иначе. Come on, попробуй ещё раз!"
            add_message("user", user_message)
            add_message("assistant", reply)
            save_last_exchange(user_message, reply)
            return reply

        # 2. Системные команды
        command_result = try_parse_command(user_message)
        if command_result is not None:
            success, message = command_result
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            return message

        # 3. Запоминание через ключевые слова
        self._check_memory_commands(user_message)

        # 4. Выученные ответы из памяти
        learned = find_learned_response(user_message)

        # 5. Поиск в интернете (если онлайн и не нашли в памяти)
        search_context = ""
        if not learned:
            search_result = _try_search(user_message)
            if search_result:
                search_context = search_result
                logger.info(f"Найдено через DDG: {search_result[:100]}...")

        # 6. ИИ-ответ
        try:
            messages = self._build_messages(user_message, search_context)
            # Добавляем выученное в контекст
            if learned:
                messages[-1]["content"] = (
                    f"{user_message}\n\n[Подсказка из памяти: {learned[:300]}]"
                )

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.75, "top_p": 0.9, "num_ctx": 4096},
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                reply = data.get("message", {}).get("content", "")
                if reply:
                    # Убираем markdown-форматирование
                    reply = _clean_reply(reply)
                    # Добавляем пометку о поиске если был
                    if search_context and "нашёл" not in reply[:30].lower():
                        prefix = get_phrase("search_result")
                        reply = f"{prefix}\n{reply}"
                    add_message("user", user_message)
                    add_message("assistant", reply)
                    save_last_exchange(user_message, reply)
                    return reply
                return "Что-то пошло не так, бро. Let me try again!"
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return f"Ошибка API Ollama: {response.status_code}"

        except requests.Timeout:
            return "Думаю слишком долго... No pain, no gain — подожди секунду, бро!"
        except requests.ConnectionError:
            return "Не могу подключиться к Ollama. Убедись что он запущен, бро!"
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return f"Ошибка: {e}"

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        if not self._initialized:
            if not self.initialize():
                yield "Бро, Ollama не запущен! Установи Ollama и запусти модель."
                return

        # 1. Фидбек
        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("learned")
            add_message("user", user_message)
            add_message("assistant", reply)
            save_last_exchange(user_message, reply)
            yield reply
            return
        elif feedback == "negative":
            reply = "Понял, бро! Запомнил — в следующий раз сделаю иначе. Come on!"
            add_message("user", user_message)
            add_message("assistant", reply)
            save_last_exchange(user_message, reply)
            yield reply
            return

        # 2. Системные команды
        command_result = try_parse_command(user_message)
        if command_result is not None:
            _, message = command_result
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            yield message
            return

        self._check_memory_commands(user_message)

        # 3. Выученные ответы
        learned = find_learned_response(user_message)

        # 4. Поиск
        search_context = ""
        if not learned:
            search_result = _try_search(user_message)
            if search_result:
                search_context = search_result

        try:
            messages = self._build_messages(user_message, search_context)
            if learned:
                messages[-1]["content"] = (
                    f"{user_message}\n\n[Подсказка из памяти: {learned[:300]}]"
                )

            # Стриминг префикса поиска
            if search_context:
                prefix = get_phrase("search_result") + "\n"
                yield prefix

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.75, "top_p": 0.9, "num_ctx": 4096},
                },
                stream=True,
                timeout=120,
            )

            full_reply = ""
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_reply += token
                            yield token
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            if full_reply:
                full_reply = _clean_reply(full_reply)
                if search_context:
                    full_reply = get_phrase("search_result") + "\n" + full_reply
                add_message("user", user_message)
                add_message("assistant", full_reply)
                save_last_exchange(user_message, full_reply)

        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"Ошибка: {e}"

    def _check_memory_commands(self, text: str):
        import re
        text_lower = text.lower()
        memory_triggers = [
            "запомни", "не забудь", "сохрани", "меня зовут",
            "моё имя", "я работаю", "мне нравится", "я люблю",
            "я не люблю", "я живу", "мой возраст",
        ]
        for trigger in memory_triggers:
            if trigger in text_lower:
                if "меня зовут" in text_lower or "моё имя" in text_lower:
                    name_match = re.search(
                        r"(меня зовут|моё имя)\s+([А-ЯЁа-яёA-Za-z]+)", text_lower
                    )
                    if name_match:
                        name = name_match.group(2).capitalize()
                        set_profile("name", name)
                        logger.info(f"Запомнено имя: {name}")
                else:
                    add_fact(text, "user_said")
                break


def _clean_reply(text: str) -> str:
    """Убрать markdown форматирование из ответа."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()
