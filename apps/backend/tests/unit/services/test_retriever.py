from __future__ import annotations

from copy import deepcopy

from app.data.mock_docs import MOCK_DOCS
from app.services.retriever import Retriever


def ids(results):
    return [item.doc["id"] for item in results]


def test_pitch_alarm_and_phrase_rank_manual_first() -> None:
    retriever = Retriever()

    assert retriever.retrieve("PITCH_COMM_LOST", top_k=3)[0].doc["id"] == "doc-001"
    assert retriever.retrieve("变桨通讯中断", top_k=3)[0].doc["id"] == "doc-001"


def test_gearbox_oil_temperature_query_ranks_procedure_first() -> None:
    results = Retriever().retrieve("齿轮箱油温高", top_k=3)

    assert results[0].doc["id"] == "doc-002"
    assert results[0].doc["doc_type_code"] == "procedure"


def test_filters_only_recall_matching_documents() -> None:
    results = Retriever().retrieve("", top_k=5, filters={"component": "齿轮箱"})

    assert ids(results) == ["doc-002"]
    assert results[0].trace["matched_filters"] == {"component": "齿轮箱"}
    assert results[0].trace["filter_score"] > 0


def test_alarm_code_filter_outweighs_document_type_filter() -> None:
    results = Retriever().retrieve(
        "",
        top_k=5,
        filters={"alarm_code": "YAW_MOTOR_OVERLOAD", "doc_type": "manual"},
    )

    assert results[0].doc["id"] == "doc-003"
    assert results[0].trace["matched_filters"] == {"alarm_code": "YAW_MOTOR_OVERLOAD"}


def test_strong_text_match_survives_filter_mismatch_with_accurate_trace() -> None:
    results = Retriever().retrieve("变桨通讯中断", top_k=5, filters={"component": "齿轮箱"})

    result_by_id = {item.doc["id"]: item for item in results}
    assert "doc-001" in result_by_id
    assert result_by_id["doc-001"].trace["matched_filters"] == {}
    assert "doc-002" in result_by_id
    assert result_by_id["doc-002"].trace["matched_filters"] == {"component": "齿轮箱"}


def test_results_are_deterministic_sorted_and_limited() -> None:
    retriever = Retriever()
    first = retriever.retrieve("报警", top_k=3)
    second = retriever.retrieve("报警", top_k=3)

    assert ids(first) == ids(second)
    assert [item.score for item in first] == [item.score for item in second]
    assert len(first) <= 3
    assert [item.score for item in first] == sorted([item.score for item in first], reverse=True)


def test_trace_contains_required_fields() -> None:
    result = Retriever().retrieve("齿轮箱油温高", top_k=1)[0]

    assert set(result.trace) >= {
        "keyword_rank",
        "semantic_rank",
        "rrf_score",
        "filter_score",
        "matched_filters",
    }
    assert isinstance(result.trace["rrf_score"], float)


def test_retrieval_does_not_mutate_mock_docs() -> None:
    before = deepcopy(MOCK_DOCS)

    Retriever().retrieve("变桨通讯中断", filters={"alarm_code": "PITCH_COMM_LOST"})

    assert MOCK_DOCS == before
    assert all("rrf_score" not in doc for doc in MOCK_DOCS)


def test_empty_input_and_invalid_top_k_are_safe() -> None:
    retriever = Retriever()

    assert retriever.retrieve("", filters={}) == []
    assert retriever.retrieve("变桨通讯中断", top_k=0) == []
    assert retriever.retrieve("变桨通讯中断", top_k=-1) == []


def test_trace_exposes_dense_rrf_reranker_and_distance() -> None:
    result = Retriever().retrieve("齿轮箱油温高", top_k=1, distance_threshold=1.0)[0]
    assert set(result.trace) >= {"bm25_rank", "dense_rank", "rrf_score", "reranker_score", "distance", "distance_threshold", "embedding_provider", "retrieval_mode"}
    assert result.trace["distance_threshold"] == 1.0


def test_distance_threshold_can_remove_dense_candidates() -> None:
    assert Retriever().retrieve("完全无关查询", top_k=5, distance_threshold=0.0) == []