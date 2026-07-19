from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol
from urllib import error, request


@dataclass
class ProviderResult:
    provider: str
    model_version: str
    status: str
    latency_ms: float
    payload: dict[str, Any]
    error: str = ""


class OCRProvider(Protocol):
    def parse_page(self, image: bytes, *, page: int = 1, text: str = "") -> ProviderResult: ...


class VisionProvider(Protocol):
    def describe(self, image: bytes, *, prompt: str = "") -> ProviderResult: ...


class EmbeddingProvider(Protocol):
    def embed(self, inputs: list[Any]) -> ProviderResult: ...


class RerankerProvider(Protocol):
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> ProviderResult: ...


class MockOCRProvider:
    def parse_page(self, image: bytes, *, page: int = 1, text: str = "") -> ProviderResult:
        return ProviderResult("mock_ocr", "offline-v1", "mock", 0.0, {"text": text, "blocks": [], "page": page, "mode": "offline_fallback"})


class MockVisionProvider:
    def describe(self, image: bytes, *, prompt: str = "") -> ProviderResult:
        return ProviderResult("mock_vision", "offline-v1", "mock", 0.0, {"caption": "离线视觉描述", "entities": [], "relations": [], "tables": [], "equipment_structures": [], "prompt": prompt, "mode": "offline_fallback"})


class HashEmbeddingProvider:
    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def _vector(self, value: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", value):
            digest = hashlib.sha256(token.lower().encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    def embed(self, inputs: list[Any]) -> ProviderResult:
        started = perf_counter()
        values = []
        for value in inputs:
            if isinstance(value, dict):
                value = value.get("text") or value.get("caption") or value.get("data", "")
            values.append(str(value))
        vectors = [self._vector(value) for value in values]
        return ProviderResult("hash_embedding", "offline-v1", "ok", (perf_counter() - started) * 1000, {"vectors": vectors, "dimensions": self.dimensions, "mode": "offline_fallback"})


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str, provider: str, timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.timeout = min(timeout, 60)

    def chat(self, messages: list[dict[str, Any]], *, response_format: dict[str, Any] | None = None) -> ProviderResult:
        started = perf_counter()
        endpoint = self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0, "stream": False}
        if response_format:
            payload["response_format"] = response_format
        try:
            req = request.Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}, method="POST")
            with request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = _extract_content(body)
            return ProviderResult(self.provider, self.model, "ok" if content else "error", (perf_counter() - started) * 1000, {"content": content or "", "raw": body})
        except (OSError, error.URLError, error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return ProviderResult(self.provider, self.model, "error", (perf_counter() - started) * 1000, {}, str(exc))


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, base_url: str, api_key: str, model: str, provider: str = "openai_compatible_embedding", timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.timeout = min(timeout, 60)

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def embed(self, inputs: list[Any]) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(self.provider, self.model or "", "disabled", 0.0, {})
        started = perf_counter()
        endpoint = self.base_url if self.base_url.endswith("/embeddings") else f"{self.base_url}/embeddings"
        normalized: list[Any] = []
        for value in inputs:
            if isinstance(value, dict) and value.get("type") == "image":
                encoded = value.get("data", "")
                if not str(encoded).startswith("data:"):
                    encoded = f"data:{value.get('mime_type', 'image/png')};base64,{encoded}"
                normalized.append({"image": encoded})
            elif isinstance(value, dict):
                normalized.append(str(value.get("text") or value.get("caption") or ""))
            else:
                normalized.append(str(value))
        try:
            req = request.Request(endpoint, data=json.dumps({"model": self.model, "input": normalized}, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}, method="POST")
            with request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            data = body.get("data", []) if isinstance(body, dict) else []
            vectors = [item.get("embedding", []) for item in data if isinstance(item, dict)]
            if len(vectors) != len(inputs):
                raise ValueError("embedding response length mismatch")
            return ProviderResult(self.provider, self.model, "ok", (perf_counter() - started) * 1000, {"vectors": vectors, "dimensions": len(vectors[0]) if vectors else 0, "mode": "remote"})
        except (OSError, error.URLError, error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return ProviderResult(self.provider, self.model, "error", (perf_counter() - started) * 1000, {}, str(exc))


def build_embedding_provider() -> tuple[EmbeddingProvider, str]:
    remote = OpenAICompatibleEmbeddingProvider(os.getenv("EMBEDDING_BASE_URL", ""), os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", ""), os.getenv("EMBEDDING_MODEL", ""))
    if remote.enabled:
        return remote, "remote"
    return HashEmbeddingProvider(int(os.getenv("EMBEDDING_FALLBACK_DIMENSIONS", "64"))), "offline_fallback"


def build_vision_provider(kind: str = "vision") -> tuple[Any, str]:
    base = os.getenv("VISION_BASE_URL", "")
    key = os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("VISION_MODEL", "qwen3-vl")
    if base and key:
        return OpenAICompatibleProvider(base, key, model, kind), "remote"
    return MockVisionProvider(), "offline_fallback"


def build_ocr_provider() -> tuple[Any, str]:
    base = os.getenv("OCR_BASE_URL", "")
    key = os.getenv("OCR_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OCR_MODEL", "dots-ocr")
    if base and key:
        return OpenAICompatibleProvider(base, key, model, "dots_ocr"), "remote"
    return MockOCRProvider(), "offline_fallback"


def _extract_content(body: dict[str, Any]) -> str | None:
    choices = body.get("choices") if isinstance(body, dict) else None
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content") or choices[0].get("text")
        if isinstance(content, list):
            content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        if isinstance(content, str) and content.strip():
            return content.strip()
    for key in ("output_text", "content"):
        content = body.get(key) if isinstance(body, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def provider_config() -> dict[str, str]:
    return {key: os.getenv(key, "") for key in ("OCR_BASE_URL", "VISION_BASE_URL", "EMBEDDING_BASE_URL", "RERANKER_BASE_URL")}