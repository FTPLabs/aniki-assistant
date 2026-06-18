"""
ИИ-движок Аники — Ollama + DuckDuckGo + обучение + полная память.
Умеет: запоминать, забывать, писать промпты, искать в интернете.
"""

import requests
import json
import re
import logging
from typing import Optional, List, Dict, Generator

from .personality import SYSTEM_PROMPT, get_phrase
from .memory import (
    get_conversation_history, add_message, build_context_string,
    add_fact, set_profile, forget_last_messages, forget_messages_about,
    clear_conversation_history, forget_facts_about, clear_all_facts,
)
from .commands import try_parse_command, PROMPT_MARKER, mark_as_prompt
from .learning import (
    save_last_exchange, find_learned_response,
    confirm_last_response, check_feedback, init_learning_table,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL   = "mistral"
FALLBACK_MODELS = ["mistral", "llama3.2", "llama3.2:3b", "llama3", "llama2",
                   "gemma2", "phi3", "deepseek"]

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
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> List[str]:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
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


# ── Команды забывания ─────────────────────────────────────────────────────────

_FORGET_PATTERNS = [
    (re.compile(r"забудь\s+(?:про\s+|о\s+)?всё|очисти\s+память|удали\s+(?:всю\s+)?(?:историю|память)", re.I),
     "all"),
    (re.compile(r"забудь\s+(?:это|последнее|последний\s+ответ)", re.I),
     "last"),
    (re.compile(r"забудь\s+(?:про\s+|о\s+|то\s+что\s+я\s+сказал\s+про\s+)?(.+)", re.I),
     "topic"),
]

_PROMPT_PATTERNS = re.compile(
    r"(?:напиши|создай|сгенерируй|придумай)\s+(?:мне\s+)?промпт\s+(?:для\s+|про\s+|о\s+|на\s+)?(.+)",
    re.I,
)

_REMIND_CHECK_RE = re.compile(
    r"(?:напомни|что\s+ты\s+знаешь\s+обо\s+мне|что\s+ты\s+помнишь)",
    re.I,
)


def _handle_forget(text: str) -> Optional[str]:
    """Обработать команду забывания. Возвращает ответ или None."""
    for pattern, kind in _FORGET_PATTERNS:
        m = pattern.search(text)
        if m:
            if kind == "all":
                n = clear_conversation_history()
                clear_all_facts()
                return ("Готово, бро! Стёр всю память — " +
                        f"удалил {n} сообщений. Fresh start, как говорится!")
            elif kind == "last":
                n = forget_last_messages(4)
                return (f"Забыл последний обмен ({n} сообщений). "
                        "Что обсуждали — не помню. Come on!")
            elif kind == "topic" and m.lastindex:
                topic = m.group(1).strip().rstrip(".,!?")
                n1 = forget_messages_about(topic)
                n2 = forget_facts_about(topic)
                total = n1 + n2
                if total:
                    return (f"Забыл всё про '{topic}' — удалил {total} записей. "
                            "Это между нами, бро!")
                else:
                    return (f"Ничего не нашёл про '{topic}' в памяти. "
                            "Может, мы и не говорили об этом?")
    return None


def _handle_memory_show(text: str) -> Optional[str]:
    """Показать что Аники знает о пользователе."""
    if _REMIND_CHECK_RE.search(text):
        context = build_context_string()
        if context:
            return f"Вот что я о тебе знаю, бро:\n\n{context}"
        return ("Я пока ничего особого о тебе не знаю, бро. "
                "Расскажи что-нибудь — например, как тебя зовут!")
    return None


def _handle_prompt_request(text: str) -> Optional[str]:
    """Если пользователь просит написать промпт — вернуть маркер."""
    m = _PROMPT_PATTERNS.search(text)
    if m:
        return m.group(1).strip()  # тема промпта
    return None


class AnikiAI:
    """Главный ИИ-движок ассистента."""

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
        logger.info(f"Модель: {self.model}")
        self._initialized = True
        return True

    def _build_messages(self, user_message: str, search_context: str = "") -> List[Dict]:
        context = build_context_string()
        system = SYSTEM_PROMPT
        if context:
            system += f"\n\nПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n{context}"
        if search_context:
            system += f"\n\nНАЙДЕНО В ИНТЕРНЕТЕ:\n{search_context}"

        messages = [{"role": "system", "content": system}]
        # Полная история — до 40 сообщений
        history = get_conversation_history(limit=40)
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _ollama_request(self, messages: List[Dict], stream: bool = False):
        return requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "options": {
                    "temperature": 0.75,
                    "top_p": 0.9,
                    "num_ctx": 8192,    # увеличен контекст
                    "repeat_penalty": 1.1,
                },
            },
            stream=stream,
            timeout=120 if stream else 90,
        )

    def chat(self, user_message: str) -> str:
        if not self._initialized:
            if not self.initialize():
                return "Бро, Ollama не запущен! Установи Ollama и запусти модель."

        # 1. Фидбек
        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("learned")
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply
        elif feedback == "negative":
            reply = "Понял, бро! Запомнил — в следующий раз сделаю иначе."
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply

        # 2. Команда забывания
        forget_reply = _handle_forget(user_message)
        if forget_reply is not None:
            add_message("user", user_message)
            add_message("assistant", forget_reply)
            return forget_reply

        # 3. Показать память
        memory_reply = _handle_memory_show(user_message)
        if memory_reply is not None:
            add_message("user", user_message)
            add_message("assistant", memory_reply)
            return memory_reply

        # 4. Системные команды
        cmd = try_parse_command(user_message)
        if cmd is not None:
            _, message = cmd
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            return message

        # 5. Запоминание
        self._check_memory_commands(user_message)

        # 6. Промпт-запрос → ИИ с особым системным промптом
        prompt_topic = _handle_prompt_request(user_message)

        # 7. Выученные ответы
        learned = find_learned_response(user_message)

        # 8. Поиск в интернете
        search_context = ""
        if not learned and not prompt_topic:
            search_result = _try_search(user_message)
            if search_result:
                search_context = search_result

        # 9. ИИ-ответ
        try:
            if prompt_topic:
                messages = self._build_prompt_messages(prompt_topic)
            else:
                messages = self._build_messages(user_message, search_context)
                if learned:
                    messages[-1]["content"] += f"\n\n[Из памяти: {learned[:300]}]"

            resp = self._ollama_request(messages, stream=False)
            if resp.status_code == 200:
                raw = resp.json().get("message", {}).get("content", "")
                if raw:
                    reply = _clean_reply(raw)
                    if prompt_topic:
                        reply = mark_as_prompt(reply)
                    elif search_context and "нашёл" not in reply[:30].lower():
                        reply = get_phrase("search_result") + "\n" + reply
                    add_message("user", user_message)
                    add_message("assistant", reply)
                    save_last_exchange(user_message, reply)
                    return reply
            return "Что-то пошло не так. Let me try again!"

        except requests.Timeout:
            return "Думаю слишком долго... No pain, no gain — подожди!"
        except requests.ConnectionError:
            return "Не могу подключиться к Ollama. Убедись что он запущен!"
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return f"Ошибка: {e}"

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        if not self._initialized:
            if not self.initialize():
                yield "Бро, Ollama не запущен!"
                return

        # 1. Фидбек
        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("learned")
            add_message("user", user_message)
            add_message("assistant", reply)
            yield reply
            return
        elif feedback == "negative":
            reply = "Понял, бро! Запомнил — в следующий раз сделаю иначе."
            add_message("user", user_message)
            add_message("assistant", reply)
            yield reply
            return

        # 2. Забывание
        forget_reply = _handle_forget(user_message)
        if forget_reply is not None:
            add_message("user", user_message)
            add_message("assistant", forget_reply)
            yield forget_reply
            return

        # 3. Показать память
        memory_reply = _handle_memory_show(user_message)
        if memory_reply is not None:
            add_message("user", user_message)
            add_message("assistant", memory_reply)
            yield memory_reply
            return

        # 4. Системные команды
        cmd = try_parse_command(user_message)
        if cmd is not None:
            _, message = cmd
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            yield message
            return

        # 5. Запоминание
        self._check_memory_commands(user_message)

        # 6. Промпт-запрос
        prompt_topic = _handle_prompt_request(user_message)

        # 7. Выученные ответы
        learned = find_learned_response(user_message)

        # 8. Поиск
        search_context = ""
        if not learned and not prompt_topic:
            sr = _try_search(user_message)
            if sr:
                search_context = sr

        try:
            if prompt_topic:
                messages = self._build_prompt_messages(prompt_topic)
                yield f"{PROMPT_MARKER}"  # маркер — UI переключится в режим промпта
            else:
                messages = self._build_messages(user_message, search_context)
                if learned:
                    messages[-1]["content"] += f"\n\n[Из памяти: {learned[:300]}]"
                if search_context:
                    yield get_phrase("search_result") + "\n"

            resp = self._ollama_request(messages, stream=True)
            full_reply = ""

            for line in resp.iter_lines():
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
                if prompt_topic:
                    full_reply = mark_as_prompt(full_reply)
                elif search_context:
                    full_reply = get_phrase("search_result") + "\n" + full_reply
                add_message("user", user_message)
                add_message("assistant", full_reply)
                save_last_exchange(user_message, full_reply)

        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"Ошибка: {e}"

    def _build_prompt_messages(self, topic: str) -> List[Dict]:
        """Построить запрос специально для написания промпта."""
        system = (
            "Ты — эксперт по написанию промптов для нейросетей. "
            "Напиши чёткий, подробный и эффективный промпт на русском языке. "
            "Только промпт — без объяснений, без предисловий, без markdown. "
            "Начни сразу с промпта."
        )
        user_msg = f"Напиши промпт для: {topic}"
        return [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ]

    def _check_memory_commands(self, text: str):
        text_lower = text.lower()
        triggers = [
            "запомни", "не забудь", "сохрани",
            "меня зовут", "моё имя", "я работаю",
            "мне нравится", "я люблю", "я не люблю",
            "я живу", "мой возраст", "я учусь",
        ]
        for trigger in triggers:
            if trigger in text_lower:
                if "меня зовут" in text_lower or "моё имя" in text_lower:
                    nm = re.search(
                        r"(?:меня зовут|моё имя)\s+([А-ЯЁа-яёA-Za-z]+)",
                        text_lower
                    )
                    if nm:
                        name = nm.group(1).capitalize()
                        set_profile("name", name)
                        logger.info(f"Запомнено имя: {name}")
                else:
                    add_fact(text, "user_said")
                break


def _clean_reply(text: str) -> str:
    """Убрать markdown из ответа ИИ."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"#{1,6}\s+",     "",    text)
    text = re.sub(r"`(.+?)`",       r"\1", text)
    text = re.sub(r"\[Из памяти:.+?\]", "", text)
    return text.strip()
