"""
Поиск DuckDuckGo для Аники — работает без API-ключей.
FIX [L1]: list[str] → List[str] для совместимости с Python 3.8+.
"""

import urllib.request
import urllib.parse
import json
import re
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


def duckduckgo_instant(query: str) -> Optional[str]:
    """Быстрый ответ через DuckDuckGo Instant Answer API."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1&kl=ru-ru"
        req = urllib.request.Request(url, headers={
            "User-Agent": "AnikiBuddy/2.0 (assistant)",
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        parts = []
        if data.get("AbstractText"):
            parts.append(data["AbstractText"])
        for topic in data.get("RelatedTopics", [])[:2]:
            if isinstance(topic, dict) and topic.get("Text"):
                parts.append(topic["Text"])

        if parts:
            return "\n".join(parts[:3])
    except Exception as e:
        logger.debug(f"DDG instant error: {e}")
    return None


def duckduckgo_html(query: str, max_results: int = 3) -> List[str]:
    """Парсинг HTML-поиска DuckDuckGo. FIX [L1]: List[str] вместо list[str]."""
    results: List[str] = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}&kl=ru-ru"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        for s in snippets[:max_results]:
            clean = re.sub(r"<[^>]+>", "", s).strip()
            if clean and len(clean) > 20:
                results.append(clean)
    except Exception as e:
        logger.debug(f"DDG html error: {e}")
    return results


def search(query: str) -> Optional[str]:
    """
    Главная функция поиска. Сначала пробует Instant Answer, потом HTML.
    Возвращает текстовый контекст для ИИ или None если ничего не нашёл.
    """
    clean_query = re.sub(r"^(аники|найди|поищи|что такое|кто такой|расскажи про|объясни)\s+", "",
                         query.lower().strip())

    result = duckduckgo_instant(clean_query)
    if result:
        return result

    snippets = duckduckgo_html(clean_query, max_results=3)
    if snippets:
        return "\n".join(snippets)

    return None


def is_online() -> bool:
    """Проверить наличие интернета."""
    try:
        urllib.request.urlopen("https://duckduckgo.com", timeout=3)
        return True
    except Exception:
        return False
