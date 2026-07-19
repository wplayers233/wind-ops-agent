from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from time import time
from typing import Any
import math
import os

from app.services.providers import build_embedding_provider
from app.services.storage import MilvusBackend, RedisBackend


@dataclass
class MemoryRecord:
    session_id: str
    role: str
    content: str
    component: str = ""
    intent: str = ""
    metadata: dict | None = None
    created_at: float = 0.0
    vector: list[float] | None = None


class MemoryStore:
    def __init__(self, short_ttl_seconds: int = 3600, short_limit: int = 12, distance_threshold: float | None = None) -> None:
        self.short_ttl_seconds = short_ttl_seconds
        self.short_limit = short_limit
        self.distance_threshold = distance_threshold if distance_threshold is not None else float(os.getenv("MEMORY_DISTANCE_THRESHOLD", "0.65"))
        self._redis_like: dict[str, dict] = {}
        self._milvus_like: list[MemoryRecord] = []
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory-write")
        self._embedding_provider, self.embedding_mode = build_embedding_provider()
        self.redis_backend = RedisBackend() if os.getenv("MEMORY_REMOTE_ENABLED", "false").lower() == "true" else None
        self.milvus_backend = MilvusBackend() if os.getenv("MEMORY_REMOTE_ENABLED", "false").lower() == "true" else None
        self.memory_mode = "redis+milvus" if self.redis_backend and self.redis_backend.available and self.milvus_backend and self.milvus_backend.available else "memory_fallback"

    def get(self, session_id: str) -> dict:
        with self._lock:
            self._purge_expired_locked(session_id)
            current = deepcopy(self._redis_like.get(session_id, self._empty_state()))
            current["long_memory"] = self.search_long_memory(session_id, current.get("context", ""), top_k=5)
            current["memory_mode"] = self.memory_mode
            current["persist_status"] = "ready"
            return current

    def update(self, session_id: str, payload: dict) -> dict:
        now = time()
        record = MemoryRecord(session_id=session_id, role=payload.get("role", "user"), content=payload.get("content", payload.get("query", "")), component=payload.get("component", "") or "", intent=payload.get("intent", "") or "", metadata=deepcopy(payload.get("metadata", {})), created_at=payload.get("created_at", now) or now)
        with self._lock:
            self._purge_expired_locked(session_id)
            current = self._redis_like.get(session_id, self._empty_state())
            current["history"].append(asdict(record))
            current["history"] = current["history"][-self.short_limit:]
            current["short_memory"] = current["history"][-min(5, self.short_limit):]
            current["summary"] = self._summarize(current["history"])
            current["context"] = self._build_context(current["history"], current["summary"])
            current["updated_at"] = now
            self._redis_like[session_id] = current
            self._milvus_like.append(record)
            self._purge_long_memory_locked(now)
            self._executor.submit(self._persist_remote, record, current)
            result = deepcopy(current)
            result["long_memory"] = self.search_long_memory(session_id, result["context"], top_k=5)
            result["memory_mode"] = self.memory_mode
            result["persist_status"] = "queued"
            return result

    def _persist_remote(self, record: MemoryRecord, state: dict) -> None:
        try:
            vector_result = self._embedding_provider.embed([{"text": record.content}])
            vector = (vector_result.payload.get("vectors") or [None])[0]
            record.vector = vector if isinstance(vector, list) else None
            if self.redis_backend and self.redis_backend.available:
                self.redis_backend.set(f"memory:{record.session_id}", state, self.short_ttl_seconds)
            if self.milvus_backend and self.milvus_backend.available:
                self.milvus_backend.upsert([{"id": f"{record.session_id}-{int(record.created_at * 1000000)}", **asdict(record), "vector": record.vector or []}])
        except Exception:
            return

    def search_long_memory(self, session_id: str, query: str, top_k: int = 5, distance_threshold: float | None = None) -> list[dict]:
        with self._lock:
            query_text = query or ""
            terms = set(query_text.lower().split())
            query_result = self._embedding_provider.embed([{"text": query_text}]) if query_text else None
            query_vector = ((query_result.payload.get("vectors") or [None])[0] if query_result and query_result.status == "ok" else None)
            threshold = self.distance_threshold if distance_threshold is None else distance_threshold
            scored: list[tuple[float, float, MemoryRecord]] = []
            for item in self._milvus_like:
                if item.session_id != session_id:
                    continue
                haystack = " ".join([item.content, item.component, item.intent, str(item.metadata or {})]).lower()
                lexical = sum(1.0 for term in terms if term and term in haystack) + (2.0 if item.component and item.component in query_text else 0.0)
                dense_similarity = self._cosine(query_vector, item.vector) if query_vector and item.vector else 0.0
                distance = 1.0 - dense_similarity if item.vector else 1.0
                if query_vector and item.vector and distance > threshold:
                    continue
                score = lexical + dense_similarity * 2.0
                if not terms and item.content:
                    score = 0.1
                if score > 0:
                    scored.append((score, distance, item))
            scored.sort(key=lambda pair: (pair[0], pair[2].created_at), reverse=True)
            return [{"role": item.role, "content": item.content, "component": item.component, "intent": item.intent, "created_at": item.created_at, "score": round(score, 2), "distance": round(distance, 6), "distance_threshold": threshold} for score, distance, item in scored[:top_k]]

    @staticmethod
    def _cosine(left: list[float] | None, right: list[float] | None) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        denom = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
        return sum(a * b for a, b in zip(left, right)) / denom if denom else 0.0

    def _empty_state(self) -> dict:
        return {"history": [], "summary": "", "short_memory": [], "long_memory": [], "context": "", "memory_mode": self.memory_mode, "persist_status": "idle"}

    def _purge_expired_locked(self, session_id: str) -> None:
        current = self._redis_like.get(session_id)
        if not current:
            return
        now = time()
        current["history"] = [item for item in current.get("history", []) if now - item.get("created_at", now) <= self.short_ttl_seconds]
        current["short_memory"] = current["history"][-min(5, self.short_limit):]
        current["summary"] = self._summarize(current["history"])
        current["context"] = self._build_context(current["history"], current["summary"])
        if current["history"]:
            self._redis_like[session_id] = current
        else:
            self._redis_like.pop(session_id, None)

    def _purge_long_memory_locked(self, now: float) -> None:
        max_age = max(self.short_ttl_seconds * 24, self.short_ttl_seconds)
        self._milvus_like = [item for item in self._milvus_like if now - item.created_at <= max_age]

    def _build_context(self, history: list[dict], summary: str) -> str:
        return "\n".join(([summary] if summary else []) + [f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history[-5:]])

    def _summarize(self, history: list[dict]) -> str:
        if not history:
            return ""
        latest_component = next((item.get("component") for item in reversed(history) if item.get("component")), "未知")
        latest_intent = next((item.get("intent") for item in reversed(history) if item.get("intent")), "未知")
        return f"已累计{len(history)}轮，最近关注部件：{latest_component}，最近意图：{latest_intent}"


memory_store = MemoryStore()