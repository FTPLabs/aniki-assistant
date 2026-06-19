"""
ИИ-движок Аники v3.0 — мульти-агент роутер + 7 специализированных агентов.
Быстрее, умнее, живее. No pain no gain!
"""

import requests
import json
import re
import logging
import threading
import time
from typing import Optional, List, Dict, Generator

from .personality import SYSTEM_PROMPT, AGENT_PROMPTS, get_phrase, classify_request
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
    "llama3.2:3b", "llama3.2", "mistral",
    "gemma2", "phi3", "deepseek", "llama3", "llama2",
]

# ── Кэш быстрых ответов (часто задаваемые) ──────────────────────────────────
_QUICK_CACHE: Dict[str, str] = {}
_QUICK_CACHE_TTL: Dict[str, float] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 300  # 5 минут

# FIX [M2]: персональные/динамические запросы не кэшируем
_NO_CACHE_PATTERNS = re.compile(
    r"(как меня зовут|что ты знаешь|что ты помнишь|напомни|погода|сейчас|сколько время)",
    re.I
)


def _cache_get(key: str) -> Optional[str]:
    if _NO_CACHE_PATTERNS.search(key): return None  # FIX [M2]
    with _CACHE_LOCK:
        if key in _QUICK_CACHE and time.time() - _QUICK_CACHE_TTL.get(key, 0) < _CACHE_TTL:
            return _QUICK_CACHE[key]
    return None


_CACHE_MAX_SIZE = 200  # FIX [M1]: лимит кэша

  def _cache_set(key: str, value: str):
      with _CACHE_LOCK:
          if len(_QUICK_CACHE) >= _CACHE_MAX_SIZE:
              now = time.time()
              stale = [k for k, t in _QUICK_CACHE_TTL.items() if now - t >= _CACHE_TTL]
              for k in stale:
                  _QUICK_CACHE.pop(k, None)
                  _QUICK_CACHE_TTL.pop(k, None)
              if len(_QUICK_CACHE) >= _CACHE_MAX_SIZE:
                  oldest = sorted(_QUICK_CACHE_TTL, key=lambda k: _QUICK_CACHE_TTL[k])[:50]
                  for k in oldest:
                      _QUICK_CACHE.pop(k, None)
                      _QUICK_CACHE_TTL.pop(k, None)
          _QUICK_CACHE[key] = value
          _QUICK_CACHE_TTL[key] = time.time()


_search_lock = threading.Lock()
_search_available: Optional[bool] = None
_search_checked_at: float = 0.0


def _try_search(query: str) -> Optional[str]:
    global _search_available, _search_checked_at
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
                return f"Забыл последний обмен ({n} сообщ.)."
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


# ── Параметры модели по типу агента — быстрее и точнее ──────────────────────
_AGENT_OPTIONS = {
    "command":    {"temperature": 0.5,  "num_predict": 64,  "top_p": 0.9},
    "search":     {"temperature": 0.6,  "num_predict": 256, "top_p": 0.9},
    "memory":     {"temperature": 0.5,  "num_predict": 128, "top_p": 0.9},
    "creative":   {"temperature": 0.9,  "num_predict": 512, "top_p": 0.95},
    "knowledge":  {"temperature": 0.65, "num_predict": 300, "top_p": 0.9},
    "chat":       {"temperature": 0.8,  "num_predict": 150, "top_p": 0.92},
    "motivation": {"temperature": 0.85, "num_predict": 150, "top_p": 0.92},
}


class AnikiAI:

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self._initialized = False
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

    def _build_messages(self, user_message: str, search_context: str = "",
                        agent_type: str = "chat") -> List[Dict]:
        context = build_context_string()
        system = AGENT_PROMPTS.get(agent_type, SYSTEM_PROMPT)
        if context:
            system += f"\n\nПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n{context}"
        if search_context:
            system += f"\n\nНАЙДЕНО В ИНТЕРНЕТЕ:\n{search_context}"
        messages = [{"role": "system", "content": system}]
        # Уменьшили историю с 40 до 20 — быстрее
        messages.extend(get_conversation_history(limit=20))
        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_prompt_messages(self, topic: str) -> List[Dict]:
        return [
            {"role": "system", "content": (
                "Ты — эксперт по промптам для нейросетей. "
                "Напиши чёткий промпт на русском. "
                "Только промпт — без объяснений."
            )},
            {"role": "user", "content": f"Промпт для: {topic}"},
        ]

    def _ollama_request(self, messages: List[Dict], stream: bool = False,
                        agent_type: str = "chat"):
        opts = _AGENT_OPTIONS.get(agent_type, _AGENT_OPTIONS["chat"])
        return requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model":    self.model,
                "messages": messages,
                "stream":   stream,
                "options": {
                    **opts,
                    "num_ctx":        4096,
                    "repeat_penalty": 1.15,
                },
            },
            stream=stream,
            timeout=90 if stream else 60,
        )

    def _pre_process(self, user_message: str):
        with self._init_lock:
            initialized = self._initialized
        if not initialized:
            if not self.initialize():
                return get_phrase("ollama_offline"), None, "", None, "chat"

        feedback = check_feedback(user_message)
        if feedback == "positive":
            confirm_last_response()
            reply = get_phrase("positive_feedback")
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply, None, "", None, "chat"
        if feedback == "negative":
            reply = get_phrase("negative_feedback")
            add_message("user", user_message)
            add_message("assistant", reply)
            return reply, None, "", None, "chat"

        forget_reply = _handle_forget(user_message)
        if forget_reply is not None:
            add_message("user", user_message)
            add_message("assistant", forget_reply)
            return forget_reply, None, "", None, "memory"

        memory_reply = _handle_memory_show(user_message)
        if memory_reply is not None:
            add_message("user", user_message)
            add_message("assistant", memory_reply)
            return memory_reply, None, "", None, "memory"

        cmd = try_parse_command(user_message)
        if cmd is not None:
            _, message = cmd
            add_message("user", user_message)
            add_message("assistant", message)
            save_last_exchange(user_message, message)
            return message, None, "", None, "command"

        _check_memory_commands(user_message)
        prompt_topic = _handle_prompt_request(user_message)
        learned = find_learned_response(user_message)

        # Мульти-агент роутинг — определяем специализацию
        agent_type = classify_request(user_message)

        search_context = ""
        if not learned and not prompt_topic and agent_type in ("search", "knowledge"):
            sr = _try_search(user_message)
            if sr:
                search_context = sr

        return None, prompt_topic, search_context, learned, agent_type

    def chat_stream(self, user_message: str) -> Generator[str, None, None]:
        early, prompt_topic, search_context, learned, agent_type = self._pre_process(user_message)
        if early is not None:
            yield early
            return

        # Быстрый кэш — не запрашиваем LLM повторно
        cache_key = f"{agent_type}:{user_message[:100]}"
        if agent_type in ("knowledge",) and not search_context and not learned:
            cached = _cache_get(cache_key)
            if cached:
                logger.debug(f"Cache hit: {cache_key[:50]}")
                yield cached
                return

        try:
            if prompt_topic:
                messages = self._build_prompt_messages(prompt_topic)
                yield PROMPT_MARKER
            else:
                messages = self._build_messages(user_message, search_context, agent_type)
                if learned:
                    messages[-1]["content"] += f"\n\n[Из памяти: {learned[:200]}]"
                if search_context:
                    yield get_phrase("search_result") + "\n"

            resp       = self._ollama_request(messages, stream=True, agent_type=agent_type)
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
                if agent_type == "knowledge" and not search_context:
                    _cache_set(cache_key, full_reply)

        except requests.Timeout:
            yield "Думаю... подожди секунду, бро!"
        except requests.ConnectionError:
            yield get_phrase("ollama_offline")
        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield get_phrase("error")

    def chat(self, user_message: str) -> str:
        result = ""
        for chunk in self.chat_stream(user_message):
            result += chunk
        return result
