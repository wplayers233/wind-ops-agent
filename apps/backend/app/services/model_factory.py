from __future__ import annotations

import os
from typing import Any


def build_chat_model() -> Any | None:
    """Create an optional LangChain model; return None for the offline path."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            temperature=0.1,
            timeout=20,
            max_retries=1,
        )
    except Exception:
        return None


def model_mode(model: Any | None) -> str:
    return "langchain" if model is not None else "rules_fallback"
