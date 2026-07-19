from __future__ import annotations

from dataclasses import dataclass
import math
import os
import re
from typing import Any


@dataclass
class HybridSearchItem:
    document: dict[str, Any]
    score: float
    matched_terms: list[str]
    matched_modalities: list[str]
    distance: float = 0.0

    @property
    def channel(self) -> str:
        return "bm25+hashed_embedding"


class BGEReranker:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("BGE_RERANKER_MODEL", "")
        self.enabled = False
        self._model = None
        if self.model_name:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                self.enabled = True
            except Exception:
                self._model = None

    @staticmethod
    def _document_text(document: dict[str, Any]) -> str:
        return " ".join(str(document.get(key, "")) for key in ("title", "component", "content", "ocr_text", "visual_caption", "alarm_code"))

    def score(self, query: str, document: dict[str, Any]) -> float:
        if not self.enabled or self._model is None:
            return 0.0
        try:
            value = self._model.predict([(query, self._document_text(document))])
            return float(value[0] if hasattr(value, "__len__") else value)
        except Exception:
            self.enabled = False
            return 0.0


class LocalHybridIndex:
    """Pure-Python BM25 fallback with Chinese character n-grams."""
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.version = "local-bm25-v4"
        self.reranker = BGEReranker()
        self._docs_tokens = [self._tokenize(self._document_text(doc)) for doc in documents]
        self._avgdl = sum(len(item) for item in self._docs_tokens) / max(1, len(self._docs_tokens))
        self._df: dict[str, int] = {}
        for tokens in self._docs_tokens:
            for token in set(tokens):
                self._df[token] = self._df.get(token, 0) + 1

    @staticmethod
    def _document_text(document: dict[str, Any]) -> str:
        return " ".join(str(document.get(key, "")) for key in ("title", "component", "content", "ocr_text", "visual_caption", "alarm_code"))

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        normalized = (value or "").lower()
        words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        ngrams = [normalized[index:index + 2] for index in range(max(0, len(normalized) - 1)) if not normalized[index].isspace() and not normalized[index + 1].isspace()]
        return words + ngrams

    @staticmethod
    def _matched_modalities(document: dict[str, Any]) -> list[str]:
        return [item for item in ["ocr" if document.get("ocr_text") else None, "vision" if document.get("visual_caption") else None, document.get("content_type")] if item]

    def _bm25(self, query_tokens: list[str], doc_index: int) -> float:
        tokens = self._docs_tokens[doc_index]
        if not tokens:
            return 0.0
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        k1, b = 1.5, 0.75
        score = 0.0
        for token in query_tokens:
            tf = counts.get(token, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(self.documents) - self._df.get(token, 0) + 0.5) / (self._df.get(token, 0) + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(tokens) / max(1, self._avgdl)))
        return score

    def search(self, query: str, top_k: int = 10) -> list[HybridSearchItem]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        scored: list[HybridSearchItem] = []
        for index, document in enumerate(self.documents):
            score = self._bm25(query_tokens, index)
            if score <= 0:
                continue
            matched = sorted(set(query_tokens) & set(self._docs_tokens[index]))
            scored.append(HybridSearchItem(document, score, matched, self._matched_modalities(document)))
        scored.sort(key=lambda item: (-item.score, item.document.get("id", "")))
        return scored[:top_k]

    def rerank(self, query: str, candidates: list[HybridSearchItem]) -> list[HybridSearchItem]:
        scores = [(item, self.reranker.score(query, item.document)) for item in candidates]
        if not any(score != 0 for _, score in scores):
            return candidates
        scores.sort(key=lambda pair: (-pair[1], pair[0].document.get("id", "")))
        return [item for item, _ in scores]