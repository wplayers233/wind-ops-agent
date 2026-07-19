from fastapi.testclient import TestClient

from app.main import app
from app.services.agent import agent


agent.llm_client.api_key = None
client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "wind-ops-agent"
    assert "version" in body


def test_metrics_endpoint_returns_metrics_payload() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert body["service_status"] == "ok"
    assert body["pipeline_status"] in {"RAG Pipeline Online", "ok", "degraded"}
    for key in ["context_precision", "context_recall", "faithfulness", "response_relevancy"]:
        assert isinstance(body[key], float)
    assert isinstance(body["session_id"], str)


def test_conversations_endpoint_returns_items_contract() -> None:
    response = client.get("/conversations")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["items"]
    first = body["items"][0]
    assert isinstance(first["id"], str)
    assert isinstance(first["title"], str)
    assert isinstance(first["meta"], dict)


def test_docs_endpoint_returns_catalog_count_and_fields() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["count"], int)
    assert body["count"] == len(body["items"])
    assert body["count"] > 0
    first = body["items"][0]
    for key in ["id", "title", "component", "doc_type", "content_type", "source", "page"]:
        assert key in first


def test_chat_endpoint_returns_structured_response() -> None:
    response = client.post(
        "/chat",
        json={"session_id": "test-session", "query": "2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "test-session"
    assert body["query"]
    assert "answer" in body and body["answer"]
    assert "intent" in body and isinstance(body["intent"], dict)
    assert "diagnosis_result" in body and isinstance(body["diagnosis_result"], dict)
    assert "evidence" in body and isinstance(body["evidence"], list)
    assert "retrieval_trace" in body and isinstance(body["retrieval_trace"], dict)
    assert "follow_up_questions" in body and isinstance(body["follow_up_questions"], list)


def test_chat_endpoint_health_check_branch_returns_fast_reply() -> None:
    response = client.post(
        "/chat",
        json={"session_id": "health-session", "query": "系统在吗"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"]["name"] == "health_check"
    assert "WindRAG" in body["answer"]
    assert "报警码" in body["answer"]


def test_retrieve_endpoint_returns_top_one_with_trace() -> None:
    response = client.post(
        "/retrieve",
        json={"query": "变桨系统通讯中断", "top_k": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "变桨系统通讯中断"
    assert body["top_k"] == 1
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 1
    first = body["results"][0]
    for key in [
        "id",
        "title",
        "component",
        "doc_type",
        "content_type",
        "source",
        "page",
        "score",
        "trace",
        "ocr_text",
        "visual_caption",
        "symptoms",
        "causes",
        "steps",
        "safety_level",
    ]:
        assert key in first
    assert isinstance(first["trace"], dict)
    assert "keyword_rank" in first["trace"]
    assert "semantic_rank" in first["trace"]


def test_retrieve_endpoint_rejects_invalid_top_k() -> None:
    response = client.post(
        "/retrieve",
        json={"query": "变桨系统通讯中断", "top_k": 0},
    )
    assert response.status_code == 422


def test_chat_endpoint_rejects_blank_query() -> None:
    response = client.post(
        "/chat",
        json={"session_id": "blank-session", "query": "   "},
    )
    assert response.status_code == 422


def test_chat_endpoint_high_risk_returns_notice() -> None:
    response = client.post(
        "/chat",
        json={"session_id": "risk-session", "query": "变桨系统通讯中断报警，需要停机检修"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "high"
    assert body["safety_notice"]
    assert "停机" in body["safety_notice"] or "安全" in body["safety_notice"]


def test_ticket_endpoint_returns_summary_with_reference() -> None:
    response = client.post(
        "/ticket",
        json={"query": "变桨系统通讯中断", "component": "变桨系统"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["summary"]
    assert body["reference"]["title"]
    assert body["reference"]["source"]
    assert isinstance(body["reference"]["page"], int)


def test_ticket_endpoint_returns_insufficient_evidence_without_false_reference() -> None:
    response = client.post(
        "/ticket",
        json={"query": "完全无关的星际推进器量子冷却问题", "component": "星际推进器"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["summary"]
    assert body["reference"] is None


def test_cors_preflight_allows_local_frontend_origin() -> None:
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_rejects_arbitrary_origin() -> None:
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers



def test_retrieve_endpoint_accepts_filters_and_distance_threshold() -> None:
    response = client.post("/retrieve", json={"query": "齿轮箱油温高", "top_k": 3, "filters": {"component": "齿轮箱"}, "distance_threshold": 1.0})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results and results[0]["component"] == "齿轮箱"
    assert results[0]["trace"]["distance_threshold"] == 1.0