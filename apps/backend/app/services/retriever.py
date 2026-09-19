from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.data.mock_docs import MOCK_DOCS
from app.services.hybrid_retrieval import LocalHybridIndex
from app.services.vector_store import MultimodalVectorStore

SYNONYMS = {"PITCH_COMM_LOST": ["变桨通讯中断", "通讯中断", "CAN异常", "变桨失联"], "变桨通讯中断": ["通讯中断", "通信故障", "CAN异常", "失联"], "齿轮箱油温高": ["齿轮箱油温过高", "油温过高", "温度报警", "冷却效率低"], "过载报警": ["电流过高", "卡滞", "负载异常"], "过压": ["母线过压", "电网波动"]}
FILTER_WEIGHTS = {"model": 2.0, "system": 4.0, "component": 4.0, "fault_domain": 3.5, "alarm_code": 8.0, "doc_type": 1.5}
RRF_K = 60


@dataclass
class RetrievedDoc:
    doc: dict
    score: float
    trace: dict


class Retriever:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = docs or MOCK_DOCS
        self.local_index = LocalHybridIndex(self.docs)
        self.vector_store = MultimodalVectorStore()
        self.vector_store.upsert(self.docs)
        self._lock = RLock()

    def replace_docs(self, docs: list[dict]) -> None:
        with self._lock:
            self.docs = docs
            self.local_index = LocalHybridIndex(self.docs)
            self.vector_store.upsert(self.docs)

    def append_docs(self, new_docs: list[dict]) -> tuple[list[dict], list[str]]:
        """Merge documents by id, skipping duplicates. Returns (added, warnings)."""
        with self._lock:
            existing_ids = {doc.get("id") for doc in self.docs}
            added: list[dict] = []
            warnings: list[str] = []
            for doc in new_docs:
                doc_id = doc.get("id")
                if doc_id in existing_ids:
                    warnings.append(f"duplicate:{doc_id}")
                    continue
                existing_ids.add(doc_id)
                added.append(doc)
            if added:
                self.docs = self.docs + added
                self.local_index = LocalHybridIndex(self.docs)
                self.vector_store.upsert(self.docs)
            return added, warnings

    def _expand_query(self, query: str) -> list[str]:
        normalized = (query or "").strip()
        terms = [normalized] + [term for term in normalized.replace("，", " ").replace(",", " ").split() if term]
        for key, values in SYNONYMS.items():
            if key in normalized:
                terms.extend(values)
        seen: set[str] = set()
        return [term for term in terms if term and not (term in seen or seen.add(term))]

    def _semantic_score(self, query: str, doc: dict) -> float:
        terms = self._expand_query(query)
        haystack = " ".join(str(doc.get(key, "")) for key in ("title", "component", "content", "ocr_text", "visual_caption", "alarm_code"))
        score = sum(1.5 for term in terms if term in haystack)
        score += sum(2.5 for symptom in doc.get("symptoms", []) if symptom in query or any(term in symptom or symptom in term for term in terms))
        score += sum(1.5 for cause in doc.get("causes", []) if cause in query or any(term in cause or cause in term for term in terms))
        if doc.get("component") and doc["component"] in query:
            score += 2.0
        return score

    def _filter_match_score(self, doc: dict, filters: dict) -> float:
        return sum(FILTER_WEIGHTS.get(key, 1.0) for key, expected in filters.items() if self._matches_filter(doc, key, expected))

    def _matches_filter(self, doc: dict, key: str, expected: Any) -> bool:
        if expected in (None, "", []):
            return False
        actual = doc.get("doc_type_code", doc.get("doc_type")) if key == "doc_type" else doc.get(key)
        return actual in expected if isinstance(expected, list) else actual == expected

    def _matched_filters(self, doc: dict, filters: dict) -> dict:
        return {key: value for key, value in filters.items() if self._matches_filter(doc, key, value)}

    @staticmethod
    def _rank(items: list[dict]) -> dict[str, int]:
        return {item["id"]: index + 1 for index, item in enumerate(items)}

    @staticmethod
    def _rrf_fuse(*rankings: list[dict], k: int = RRF_K) -> dict[str, float]:
        scores: dict[str, float] = defaultdict(float)
        for ranked in rankings:
            for index, doc in enumerate(ranked):
                scores[doc["id"]] += 1.0 / (k + index + 1)
        return dict(scores)

    def retrieve(self, query: str, top_k: int = 5, filters: dict | None = None, distance_threshold: float | None = None) -> list[RetrievedDoc]:
        filters = {key: value for key, value in (filters or {}).items() if value not in (None, "", [])}
        query = (query or "").strip()
        if top_k < 1 or (not query and not filters):
            return []
        bm25_items = self.local_index.search(query, top_k=max(top_k, 20)) if query else []
        bm25_ranked = [item.document for item in bm25_items]
        rule_semantic_ranked = sorted([doc for doc in self.docs if self._semantic_score(query, doc) > 0], key=lambda doc: (-self._semantic_score(query, doc), doc.get("id", ""))) if query else []
        dense_items = self.vector_store.search(query, top_k=max(top_k, 20), distance_threshold=distance_threshold) if query else []
        dense_ranked = [item["doc"] for item in dense_items]
        rrf_scores = self._rrf_fuse(bm25_ranked, dense_ranked)
        rrf_scores.update({doc_id: score + 0.25 / (RRF_K + rank) for doc_id, rank in self._rank(rule_semantic_ranked).items() for score in [rrf_scores.get(doc_id, 0.0)]})
        bm25_ranks, dense_ranks, semantic_ranks = self._rank(bm25_ranked), self._rank(dense_ranked), self._rank(rule_semantic_ranked)
        dense_by_id = {item["doc"]["id"]: item for item in dense_items}
        candidates = [doc for doc in self.docs if rrf_scores.get(doc["id"], 0) > 0 or self._filter_match_score(doc, filters) > 0]
        reranker = self.local_index.reranker
        rerank_scores = {doc["id"]: reranker.score(query, doc) for doc in candidates} if query else {}
        has_rerank = any(score != 0 for score in rerank_scores.values())
        results: list[RetrievedDoc] = []
        for doc in candidates:
            filter_score = self._filter_match_score(doc, filters)
            dense = dense_by_id.get(doc["id"], {})
            distance = float(dense.get("distance", 1.0)) if dense else None
            if distance_threshold is not None and (distance is None or distance > distance_threshold):
                continue
            rerank_score = rerank_scores.get(doc["id"], 0.0)
            base = rrf_scores.get(doc["id"], 0.0) * 100 + filter_score * 2 + float(dense.get("score", 0.0)) * 20
            final_score = base + (rerank_score * 10 if has_rerank else 0)
            results.append(RetrievedDoc(doc, round(final_score, 8), {"keyword_rank": bm25_ranks.get(doc["id"]), "bm25_rank": bm25_ranks.get(doc["id"]), "semantic_rank": semantic_ranks.get(doc["id"]), "dense_rank": dense_ranks.get(doc["id"]), "rrf_score": round(rrf_scores.get(doc["id"], 0.0), 8), "reranker_score": round(rerank_score, 6), "reranker": reranker.model_name if has_rerank else "disabled", "distance": round(distance, 6) if distance is not None else None, "distance_threshold": distance_threshold, "vector_rank": dense_ranks.get(doc["id"]), "vector_score": round(float(dense.get("score", 0.0)), 6), "filter_score": round(filter_score, 2), "matched_filters": self._matched_filters(doc, filters), "matched_modalities": [item for item in ["ocr" if doc.get("ocr_text") else None, "vision" if doc.get("visual_caption") else None, doc.get("content_type")] if item], "reranker_status": "enabled" if has_rerank else "disabled", "embedding_provider": dense.get("embedding_provider", self.vector_store.provider_name), "retrieval_mode": "bm25+dense+metadata_filter+rrf+bge_reranker" if has_rerank else "bm25+dense+metadata_filter+rrf", "index_version": self.local_index.version}))
        results.sort(key=lambda item: (-item.score, item.doc.get("id", "")))
        return results[:top_k]


retriever = Retriever()
