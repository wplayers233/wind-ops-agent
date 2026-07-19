from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from typing import Any
from urllib import error, request


DEFAULT_OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_TIMEOUT_SECONDS = 20


class LLMClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, timeout: int = MAX_TIMEOUT_SECONDS) -> None:
        self.api_key = api_key if api_key is not None else (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"))
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_CHAT_COMPLETIONS_URL
        self.model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.timeout = min(timeout, MAX_TIMEOUT_SECONDS)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate(self, *, query: str, intent: Any, diagnosis_result: dict[str, Any] | None, safety: dict[str, Any] | None) -> str | None:
        if not self.enabled:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是风电运维助手，请用中文输出简洁、准确、可执行的排查建议，必须遵守编排层提供的安全要求，不编造引用。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "intent": _to_plain(intent),
                            "diagnosis_result": diagnosis_result or {},
                            "safety": safety or {},
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.2,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for endpoint in self._endpoints():
            try:
                req = request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                with request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                content = self._extract_content(body)
                if content:
                    return content
            except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError, KeyError):
                continue
        return None

    def _endpoints(self) -> list[str]:
        base = self.base_url.rstrip("/")
        candidates = [base]
        if not base.endswith("/chat/completions"):
            candidates.append(f"{base}/chat/completions")
        if "api.openai.com" in base and not base.endswith("/v1/chat/completions"):
            candidates.append(DEFAULT_OPENAI_CHAT_COMPLETIONS_URL)

        result: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _extract_content(self, body: dict[str, Any]) -> str | None:
        if not isinstance(body, dict):
            return None
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            content = message.get("content") or first.get("text")
            if isinstance(content, str) and content.strip():
                return content.strip()
        for key in ("output_text", "content"):
            content = body.get(key)
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None


def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value
