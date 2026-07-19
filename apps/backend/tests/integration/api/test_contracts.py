from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ChatRequest


client = TestClient(app)


def test_health_returns_stable_contract() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "wind-ops-agent",
        "version": app.version,
    }


def test_chat_rejects_blank_query() -> None:
    response = client.post("/chat", json={"session_id": "contract", "query": "   "})

    assert response.status_code == 422


def test_retrieve_rejects_top_k_below_range() -> None:
    response = client.post("/retrieve", json={"query": "变桨系统通讯中断", "top_k": 0})

    assert response.status_code == 422


def test_retrieve_rejects_top_k_above_range() -> None:
    response = client.post("/retrieve", json={"query": "变桨系统通讯中断", "top_k": 11})

    assert response.status_code == 422


def test_compat_chat_request_uses_schema_definition() -> None:
    from app.models import ChatRequest as CompatChatRequest

    assert CompatChatRequest is ChatRequest
