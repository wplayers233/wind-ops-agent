from __future__ import annotations

from math import sqrt
from typing import Any

from app.services.providers import HashEmbeddingProvider, build_embedding_provider


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    denom = sqrt(sum(a * a for a in left)) * sqrt(sum(b * b for b in right))
    return numerator / denom if denom else 0.0


class MultimodalVectorStore:
    def __init__(self, embedding_provider: Any | None = None) -> None:
        self.documents: list[dict[str, Any]] = []
        self.vectors: dict[str, list[float]] = {}
        self.version = "multimodal-dense-v3"
        self.embedding_provider, self.embedding_mode = (embedding_provider, "injected") if embedding_provider else build_embedding_provider()
        self.provider_name = getattr(self.embedding_provider, "provider", "hash_embedding")

    def _inputs_for(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        inputs = [{"text": " ".join(str(doc.get(key, "")) for key in ("title", "component", "content", "doc_type", "source"))}]
        if doc.get("ocr_text"):
            inputs.append({"text": str(doc.get("ocr_text", "")), "modality": "ocr"})
        if doc.get("visual_caption"):
            inputs.append({"text": str(doc.get("visual_caption", "")), "modality": "vision"})
        for region in doc.get("regions", []):
            region_text = " ".join(str(region.get(key, "")) for key in ("text", "caption", "modality", "source"))
            if region_text.strip():
                inputs.append({"text": region_text, "modality": str(region.get("modality", "region"))})
        return inputs

    def upsert(self, documents: list[dict[str, Any]]) -> None:
        self.documents = list(documents)
        payloads: list[dict[str, Any]] = []
        mapping: list[str] = []
        for doc in self.documents:
            for item in self._inputs_for(doc):
                payloads.append(item)
                mapping.append(doc["id"])
        result = self.embedding_provider.embed(payloads)
        if result.status != "ok":
            fallback = HashEmbeddingProvider()
            self.embedding_provider, self.embedding_mode = fallback, "offline_fallback"
            result = fallback.embed(payloads)
        vectors = result.payload.get("vectors", [])
        self.provider_name = result.provider
        aggregated: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for doc_id, vector in zip(mapping, vectors):
            if not isinstance(vector, list):
                continue
            if doc_id not in aggregated:
                aggregated[doc_id] = [0.0] * len(vector)
                counts[doc_id] = 0
            aggregated[doc_id] = [left + right for left, right in zip(aggregated[doc_id], vector)]
            counts[doc_id] += 1
        self.vectors = {doc_id: [value / counts[doc_id] for value in vector] for doc_id, vector in aggregated.items() if counts.get(doc_id)}

    def search(self, query: str, top_k: int = 10, distance_threshold: float | None = None) -> list[dict[str, Any]]:
        if not query:
            return []
        result = self.embedding_provider.embed([{"text": query}])
        if result.status != "ok":
            return []
        query_vector = (result.payload.get("vectors") or [[]])[0]
        scored = []
        for doc in self.documents:
            similarity = _cosine(query_vector, self.vectors.get(doc["id"], []))
            distance = 1.0 - similarity
            if similarity <= 0 or (distance_threshold is not None and distance > distance_threshold):
                continue
            scored.append({"doc": doc, "score": similarity, "distance": distance, "channel": "dense", "embedding_provider": self.provider_name})
        scored.sort(key=lambda item: (-item["score"], item["doc"]["id"]))
        return scored[:top_k]
