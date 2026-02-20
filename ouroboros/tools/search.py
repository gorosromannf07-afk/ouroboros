"""Web search tool — uses OpenRouter search-capable models.

Primary:  openai/gpt-4o-mini-search-preview  (cheapest, $0.15/$0.60 per 1M)
Fallback: perplexity/sonar                   ($1/$1 per 1M)

No external API keys required beyond OPENROUTER_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import requests

from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)

_PRIMARY_MODEL = "openai/gpt-4o-mini-search-preview"
_FALLBACK_MODEL = "perplexity/sonar"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_openrouter(api_key: str, model: str, query: str) -> str:
    """Call an OpenRouter search-capable model. Returns text answer."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://colab.research.google.com/",
        "X-Title": "Ouroboros",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 1024,
    }
    resp = requests.post(_OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return msg.get("content") or ""


def _web_search(ctx: ToolContext, query: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "OPENROUTER_API_KEY not set; web_search unavailable."})

    model = os.environ.get("OUROBOROS_WEBSEARCH_MODEL", _PRIMARY_MODEL)

    try:
        answer = _call_openrouter(api_key, model, query)
        if answer:
            return json.dumps({"answer": answer}, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("web_search primary model %s failed: %s — trying fallback", model, e)

    # Fallback to perplexity/sonar
    if model != _FALLBACK_MODEL:
        try:
            answer = _call_openrouter(api_key, _FALLBACK_MODEL, query)
            if answer:
                return json.dumps({"answer": answer, "model": _FALLBACK_MODEL}, ensure_ascii=False, indent=2)
        except Exception as e2:
            return json.dumps({"error": f"Both search models failed. Last error: {repr(e2)}"}, ensure_ascii=False)

    return json.dumps({"error": "web_search returned empty answer"}, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("web_search", {
            "name": "web_search",
            "description": "Search the web via OpenAI/Perplexity search models on OpenRouter. Returns JSON with answer + sources.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        }, _web_search),
    ]
