from __future__ import annotations

import json
import os
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from etl.utils.llm_summary import load_llm_config
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _completion_url(provider: str) -> str | None:
    configured = str(os.getenv("LLM_BASE_URL") or "").strip()
    if configured:
        base = configured.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
    if provider == "openai":
        return "https://api.openai.com/v1/chat/completions"
    return None


def chat_completion(
    messages: Iterable[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 240,
) -> str | None:
    config = load_llm_config()
    if not config.enabled or not config.api_key:
        return None
    url = _completion_url(config.provider)
    if not url:
        LOGGER.warning("Unsupported LLM provider for chat completion: %s", config.provider)
        return None

    payload = {
        "model": config.model,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        LOGGER.warning("LLM chat completion failed: %s", exc)
        return None

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content.strip() or None
