"""
ИИ-движок Аники v2.3 — qwen2.5:7b + краткие ответы + память + поиск.
FIX [C1/H1]: _init_lock + _search_lock — thread-safe доступ к _initialized и search globals.
"""

import requests
import json
import re
import logging
import threading
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

DEFAULT_MODEL = "qwen2.5:7b"

FALLBACK_MODELS = [
    "qwen2.5:7b", "qwen2.5:3b", "qwen2.5",
    "llama3.2:3b", "llama3.2",
    "mistral", "gemma2", "phi3", "deepseek", "llama3", "llama2",
]

# FIX [H1]: защищаем глобалы поиска отдельным локом
_search_lock = threading.Lock()
_search_available: Optional[bool] = None
_search_checked_at: float = 0.0


def _try_search(query: str) -> Optional[str]:
    global _search_available, _search_checked_at
    import time
    now = time.time()
    with _search_lock:
        if _search_available is None or (now - _search_checked_at) > 300:
            try:
                from .search import is_online
                _search_available = is_online()
                _search_checked_at = now
            except Exception:
                _search_available = False
        available = _search_available
    if not available:
        return None
    try:
        from .search import search
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
            if preferred.split(":")[0] in model.lower():
                return model
    return available[0]


_FORGET_PATTERNS = [
    (re.compile(r"забудь\s+(?:про\s+|о\s+)?всё|очисти\s+память|удали\s+(?:всю\s+)?(?:историю|память)", re.I), "all"),
    (re.compile(r"забудь\s+(?:это|последнее|последний\s+ответ)", re.I), "last"),
    (re.compile(r"забудь\s+(?:про\s+|о\s+|то\s+что\s+я\s+сказал\s+про\s+)?(.+)", re.I), "topic"),
]

_PROMPT_PATTERNS = re.compile(
    r"(?:напиши|создай|сгенерируй|придумай)\s+(?:мне\s+)?промпт\s+(?:для\s+|про\s+|о\s+|на\s+)?(.+)", re.I
)
_REMIND_CHECK_RE = re.compile(
    r"(?:напомни|что\s+ты\s+знаешь\s+обо\s+мне|что\s+ты\s+помнишь)", re.I
)
_NAME_RE = re.compile(
    r"(?:меня\s+зовут|моё\s+имя)\s+([a-zа-яёA-ZА-ЯЁ]+)", re.I
)


def _handle_forget(text: str) -> Optional[str]:
    for pattern, kind in _FORGET_PATTERNS:
        m = pattern.search(text)
        if m:
            if kind == "all":
                n = clear_conversation_history()
                clear_all_facts()
                return f"Стёр всё — {n} сообщений. Fresh start!"
            elif kind == "last":
                n = forget_last_messages(4)
                return f"Забыл последний обмен ({n} сообщ.). Come on!"
            elif kind == "topic" and m.lastindex:
                topic = m.group(1).strip().rstrip(".,!?")
                total = forget_messages_about(topic) + forget_facts_about(topic)
                return (f"Забыл про '{topic}' — {total} записей."
                        if total else f"Ничего не нашёл про '{topic}'.")
    return None


def _handle_memory_show(text: str) -> Optional[str]:
    if _REMIND_CHECK_RE.search(text):
        context = build_context_string()
        if context:
            return f"Вот что знаю о тебе:\n\n{context}"
        return "Пока ничего не знаю о тебе. Расскажи!"
    return None


def _handle_prompt_request(text: str) -> Optional[str]:
    m = _PROMPT_PATTERNS.search(text)
    return m.group(1).strip() if m else None


def _check_memory_commands(text: str):
    triggers = [
        "запомни", "не забудь", "сохрани",
        "меня зовут", "моё имя", "я работаю",
        "мне нравится", "я люблю", "я не люблю",
        "я живу", "мой возраст", "я учусь",
    ]
    text_lower = text.lower()
    for trigger in triggers:
        if trigger in text_lower:
            nm = _NAME_RE.search(text)
            if nm:
                name = nm.group(1).strip().capitalize()
                set_profile("name", name)
                logger.info(f"Запомнено имя: {name}")
            else:
                add_fact(text, "user_said")
            break


def _clean_reply(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"#{1,6}\s+",     "",    text)
    text = re.sub(r"`(.+?)`",       r"\1", text)
    text = re.sub(r"\[Из памяти:.+?\]", "", text)
    return text.strip()


class AnikiAI:

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self._initialized = False
        # FIX [H1]: лок для безопасного доступа к _initialized из разных потоков
        self._init_lock = threading.Lock()
        init_learning_table()

    def initialize(self) -> bool:
        with self._init_lock:
            if self._initialized:
                return True
            if not check_ollama_available():
                logger.error("Ollama не запущен!")
                return False
            if not self.model:
                self.model = get_best_model()
            logger.info(f"Модель: {self.model}")
            self._initialized = True
            return True

    def _build_messages(self, user_message: str, search_context: str = "") -> List[Dict]:
        context = build_context_string()
        system  = SYSTEM_PROMPT
        if context:
            system += f"\n\nПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n{context}"
        if search_context:
            system += f"\n\nНАЙДЕНО В ИНТЕРНЕТЕ:\n{search_context}"
        messages = [{"role": "system", "content": system}]
        messages.extend(get_conversation_history(limit=40))
        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_prompt_messages(self, topic: str) -> List[Dict]:
        return [
            {"role": "system", "content": (
                "Ты — эксперт по промптам для нейросетей. "
                "Напиши чёткий промпт на русском. "
                "Только промпт — без объяснений. Начни сразу с промпта."
            )},
            {"role": "user", "content": f"Промпт для: {topic}"},
        ]

    def _ollama_request(self, messages: List[Dict], stream: bool = False):
        return requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model":    self.model,
                "messages": messages,
                "stream":   stream,
                "options": {
                    "temperature":    0.7,
                    "top_p":          0.9,
                    "num_ctx":        8192,
                    "repeat_penalty": 1.1,
                    "num_predict":    256,
                },
            },
            stream=stream,
            timeout=120 if stream else 90,
        )

    def _pre_process(self, user_message: str):
        with self._init_lock:
            initialized = self._initialized
        if not initialized:
            if not self.initialize():
                return "Бро, Ollama не запущен! Установи и запусти модель.", None, "", None

        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("learned")
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply, None, "", None
        if feedback == "negative":
            reply = "Понял! Запомнил — исправлюсь."
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply, None, "", None

        forget_reply = _handle_forget(user_message)
        if forget_reply is not None:
            add_message("user", user_message)
            add_message("assistant", forget_reply)
            return forget_reply, None, "", None

        memory_reply = _handle_memory_show(user_message)
        if memory_reply is not None:
            add_message("user", user_message)
            add_message("assistant", memory_reply)
            return memory_reply, None, "", None

        cmd = try_parse_command(user_message)
        if cmd is not None:
            _, message = cmd
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            return message, None, "", None

        _check_memory_commands(user_message)
        prompt_topic   = _handle_prompt_request(user_message)
        learned        = find_learned_response(user_message)
        search_context = ""
        if not learned and not prompt_topic:
            sr = _try_search(user_message)
            if sr:
                search_context = sr

        return None, prompt_topic, search_context, learned

    def chat(self, user_message: str) -> str:
        early, prompt_topic, search_context, learned = self._pre_process(user_message)
        if early is not None:
            return early

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
                    elif search_context:
                        reply = get_phrase("search_result") + "\n" + reply
                    add_message("user", user_message)
                    add_message("assistant", reply)
                    save_last_exchange(user_message, reply)
                    return reply
            return "Что-то пошло не так. Let me try again!"

        except requests.Timeout:
            return "Думаю... No pain no gain — подожди!"
        except requests.ConnectionError:
            return "Ollama недоступен. Убедись что запущен!"
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return f"Ошибка: {e}"

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        early, prompt_topic, search_context, learned = self._pre_process(user_message)
        if early is not None:
            yield early
            return

        try:
            if prompt_topic:
                messages = self._build_prompt_messages(prompt_topic)
                yield PROMPT_MARKER
            else:
                messages = self._build_messages(user_message, search_context)
                if learned:
                    messages[-1]["content"] += f"\n\n[Из памяти: {learned[:300]}]"
                if search_context:
                    yield get_phrase("search_result") + "\n"

            resp       = self._ollama_request(messages, stream=True)
            full_reply = ""

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data  = json.loads(line)
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
                add_message("user", user_message)
                add_message("assistant", full_reply)
                save_last_exchange(user_message, full_reply)

        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"Ошибка: {e}"
