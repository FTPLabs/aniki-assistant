"""
ИИ-движок Аники — интеграция с Ollama (локальный LLM).
"""

import requests
import json
import logging
from typing import Optional, List, Dict, Generator
from .personality import SYSTEM_PROMPT
from .memory import get_conversation_history, add_message, build_context_string, add_fact, set_profile
from .commands import try_parse_command

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "mistral"
FALLBACK_MODELS = ["mistral", "llama3.2", "llama3.2:3b", "llama3", "llama2", "gemma2", "phi3"]


def check_ollama_available() -> bool:
    """Проверить доступность Ollama."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def get_available_models() -> List[str]:
    """Получить список доступных моделей."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def get_best_model() -> str:
    """Выбрать лучшую доступную модель."""
    available = get_available_models()
    if not available:
        return DEFAULT_MODEL

    for preferred in FALLBACK_MODELS:
        for model in available:
            if preferred in model.lower():
                return model

    return available[0]


def pull_model(model_name: str) -> bool:
    """Загрузить модель через Ollama."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=300
        )
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if data.get("status") == "success":
                    return True
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}")
        return False


class AnikiAI:
    """Главный ИИ-движок ассистента."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self._initialized = False

    def initialize(self) -> bool:
        """Инициализировать ИИ."""
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

    def _build_messages(self, user_message: str) -> List[Dict]:
        """Собрать список сообщений для ИИ."""
        context = build_context_string()

        system = SYSTEM_PROMPT
        if context:
            system += f"\n\n{context}"

        messages = [{"role": "system", "content": system}]

        history = get_conversation_history(limit=10)
        messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        return messages

    def chat(self, user_message: str) -> str:
        """
        Отправить сообщение и получить ответ.
        Сначала проверяет системные команды, потом идёт к ИИ.
        """
        if not self._initialized:
            if not self.initialize():
                return "Бро, Ollama не запущен! Установи Ollama и запусти модель."

        command_result = try_parse_command(user_message)
        if command_result is not None:
            success, message = command_result
            add_message("user", user_message)
            add_message("assistant", message)
            return message

        self._check_memory_commands(user_message)

        try:
            messages = self._build_messages(user_message)

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                reply = data.get("message", {}).get("content", "")

                if reply:
                    add_message("user", user_message)
                    add_message("assistant", reply)
                    return reply
                else:
                    return "Что-то пошло не так, бро. Let me try again!"

            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Ошибка API: {response.status_code}"

        except requests.Timeout:
            return "Думаю... немного медленновато. No pain, no gain — подожди секунду!"
        except requests.ConnectionError:
            return "Не могу подключиться к Ollama. Убедись что он запущен, бро!"
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return f"Что-то пошло не так: {e}"

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        """Стриминговый ответ ИИ (по токенам)."""
        if not self._initialized:
            if not self.initialize():
                yield "Бро, Ollama не запущен! Установи Ollama и запусти модель."
                return

        command_result = try_parse_command(user_message)
        if command_result is not None:
            _, message = command_result
            add_message("user", user_message)
            add_message("assistant", message)
            yield message
            return

        self._check_memory_commands(user_message)

        try:
            messages = self._build_messages(user_message)

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.8,
                        "top_p": 0.9,
                        "num_ctx": 4096,
                    }
                },
                stream=True,
                timeout=120
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
                add_message("user", user_message)
                add_message("assistant", full_reply)

        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"Ошибка: {e}"

    def _check_memory_commands(self, text: str):
        """Проверить и обработать команды памяти."""
        text_lower = text.lower()

        memory_triggers = [
            "запомни", "запомни что", "не забудь", "сохрани",
            "меня зовут", "моё имя", "я работаю", "мне нравится",
            "я люблю", "я не люблю", "я живу", "мой возраст",
        ]

        for trigger in memory_triggers:
            if trigger in text_lower:
                if "меня зовут" in text_lower or "моё имя" in text_lower:
                    import re
                    name_match = re.search(r"(меня зовут|моё имя)\s+([А-ЯЁа-яёA-Za-z]+)", text_lower)
                    if name_match:
                        name = name_match.group(2).capitalize()
                        set_profile("name", name)
                        logger.info(f"Запомнено имя: {name}")
                else:
                    add_fact(text, "user_said")
                break
