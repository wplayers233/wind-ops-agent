from __future__ import annotations

import json
import os
from typing import Any, Protocol


class MemoryBackend(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any], ttl_seconds: int = 3600) -> None: ...


class VectorBackend(Protocol):
    def upsert(self, records: list[dict[str, Any]]) -> int: ...
    def search(self, vector: list[float], top_k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class InMemoryBackend:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.items.get(key)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int = 3600) -> None:
        self.items[key] = {**value, "_ttl_seconds": ttl_seconds}


class RedisBackend:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        try:
            import redis
            self._client = redis.Redis.from_url(self.url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        value = self._client.get(key)
        return json.loads(value) if value else None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int = 3600) -> None:
        if self.available:
            self._client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))


class MilvusBackend:
    def __init__(self, uri: str | None = None, collection: str = "wind_ops_memory") -> None:
        self.uri = uri or os.getenv("MILVUS_URI", "http://localhost:19530")
        self.collection = collection
        self._client = None
        try:
            from pymilvus import MilvusClient
            self._client = MilvusClient(uri=self.uri)
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self._client is not None

    def _ensure_collection(self, dimensions: int) -> None:
        if not self._client or self._client.has_collection(collection_name=self.collection):
            return
        self._client.create_collection(collection_name=self.collection, dimension=dimensions, metric_type="COSINE", consistency_level="Strong", auto_id=False, primary_field_name="id", vector_field_name="vector")

    def upsert(self, records: list[dict[str, Any]]) -> int:
        if not self._client or not records:
            return 0
        vectors = [record.get("vector", []) for record in records]
        if not vectors or not vectors[0]:
            return 0
        try:
            self._ensure_collection(len(vectors[0]))
            self._client.upsert(collection_name=self.collection, data=records)
            return len(records)
        except Exception:
            return 0

    def search(self, vector: list[float], top_k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self._client or not vector:
            return []
        expr_parts = []
        for key, value in (filters or {}).items():
            escaped = str(value).replace('"', '\\"')
            expr_parts.append(f'{key} == "{escaped}"')
        try:
            return self._client.search(collection_name=self.collection, data=[vector], limit=top_k, filter=" and ".join(expr_parts) or None, output_fields=["*"])[0]
        except Exception:
            return []