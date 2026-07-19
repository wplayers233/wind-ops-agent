from __future__ import annotations

import json
from urllib import error

import pytest

from app.services import agent as agent_module
from app.services.agent import COMMON_RESPONSE_KEYS, WindOpsAgent
from app.services.memory import memory_store
from app.services.retriever import RetrievedDoc


DOC = {
    "id": "doc-1",
    "title": "变流器直流母线过压处理规程",
    "model": "2.5MW",
    "system": "converter_system",
    "component": "变流器",
    "fault_domain": "over_voltage",
    "alarm_code": "CONV_DC_OV",
    "doc_type": "procedure",
    "doc_type_code": "PROC",
    "source": "规程A",
    "page": 12,
    "content_type": "text",
    "ocr_text": "直流母线过压需要停机断电挂牌后检查。",
    "visual_caption": "变流器柜检查示意图",
    "symptoms": ["直流母线过压", "跳闸"],
    "causes": ["电网波动", "制动单元异常"],
    "steps": ["确认停机、断电、挂牌", "检查直流母线电压", "检查制动单元"],
    "tools": ["万用表"],
    "spare_parts": ["制动电阻"],
    "safety_level": "high",
}


class SpyRetriever:
    def __init__(self, results: list[RetrievedDoc] | None = None) -> None:
        self.results = results or []
        self.calls: list[tuple[str, dict]] = []

    def retrieve(self, query: str, filters: dict | None = None):
        self.calls.append((query, filters or {}))
        return self.results


class StubLLM:
    def __init__(self, content: str | None = None) -> None:
        self.content = content
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        return self.content


@pytest.fixture(autouse=True)
def clear_memory(monkeypatch):
    memory_store._redis_like.clear()
    memory_store._milvus_like.clear()
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever())
    yield
    memory_store._redis_like.clear()
    memory_store._milvus_like.clear()


def assert_common_shape(response: dict) -> None:
    assert set(response) == COMMON_RESPONSE_KEYS
    assert 0 <= response["confidence"] <= 1
    assert isinstance(response["diagnosis_result"], dict)
    assert isinstance(response["retrieval_trace"], dict)
    assert isinstance(response["follow_up_questions"], list)
    assert len(response["follow_up_questions"]) == len(set(response["follow_up_questions"]))


def test_health_check_skips_retrieval_and_llm(monkeypatch) -> None:
    spy_retriever = SpyRetriever()
    monkeypatch.setattr(agent_module, "retriever", spy_retriever)
    llm = StubLLM("模型答案")

    response = WindOpsAgent(llm_client=llm).chat("s-health", "系统在吗")

    assert_common_shape(response)
    assert response["intent"]["name"] == "health_check"
    assert response["llm_used"] is False
    assert spy_retriever.calls == []
    assert llm.calls == 0


def test_missing_slots_returns_clarification_without_fake_diagnosis(monkeypatch) -> None:
    spy_retriever = SpyRetriever()
    monkeypatch.setattr(agent_module, "retriever", spy_retriever)
    llm = StubLLM("模型答案")

    response = WindOpsAgent(llm_client=llm).chat("s-clarify", "怎么排查？")

    assert_common_shape(response)
    assert response["llm_used"] is False
    assert response["evidence"] == []
    assert response["diagnosis_result"]["candidate_causes"] == []
    assert response["follow_up_questions"]
    assert spy_retriever.calls == []
    assert llm.calls == 0


def test_normal_diagnosis_calls_nodes_and_writes_two_memory_records(monkeypatch) -> None:
    spy_retriever = SpyRetriever([RetrievedDoc(DOC, 2.5, {"keyword": 1.0})])
    monkeypatch.setattr(agent_module, "retriever", spy_retriever)

    response = WindOpsAgent(llm_client=StubLLM()).chat("s-normal", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")

    assert_common_shape(response)
    assert len(spy_retriever.calls) == 1
    assert spy_retriever.calls[0][1]["system"] == "converter_system"
    assert response["diagnosis_result"]["citations"]
    state = memory_store.get("s-normal")
    assert len(state["history"]) == 2
    assert [item["role"] for item in state["history"]] == ["user", "assistant"]


def test_no_evidence_returns_rule_fallback_with_empty_citations(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([]))

    response = WindOpsAgent(llm_client=StubLLM()).chat("s-empty", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")

    assert_common_shape(response)
    assert response["llm_used"] is False
    assert response["evidence"] == []
    assert response["diagnosis_result"]["citations"] == []
    assert response["confidence"] <= 0.55
    assert "未检索到足够证据" in response["answer"]


def test_unconfigured_llm_sets_llm_used_false(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([RetrievedDoc(DOC, 2.5, {})]))

    response = WindOpsAgent(llm_client=StubLLM()).chat("s-no-key", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")

    assert_common_shape(response)
    assert response["llm_used"] is False


def test_llm_success_sets_llm_used_true(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([RetrievedDoc(DOC, 2.5, {})]))

    response = WindOpsAgent(llm_client=StubLLM("确认停机、断电、挂牌后，检查母线电压。" )).chat(
        "s-llm", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？"
    )

    assert_common_shape(response)
    assert response["llm_used"] is True
    assert "检查母线电压" in response["answer"]


@pytest.mark.parametrize(
    "body,exc",
    [
        ({"error": "bad"}, error.HTTPError("http://llm", 500, "boom", {}, None)),
        ({"error": "timeout"}, TimeoutError("timeout")),
        ("not-json", None),
        ({"choices": [{"message": {"content": "   "}}]}, None),
    ],
)
def test_llm_http_timeout_bad_json_and_empty_text_degrade(monkeypatch, body, exc) -> None:
    from app.services.llm_client import LLMClient

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            if isinstance(body, str):
                return body.encode("utf-8")
            return json.dumps(body).encode("utf-8")

    def fake_urlopen(*args, **kwargs):
        if exc:
            raise exc
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_client.request.urlopen", fake_urlopen)
    client = LLMClient(api_key="test-key", base_url="http://llm.example/v1", timeout=20)
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([RetrievedDoc(DOC, 2.5, {})]))

    response = WindOpsAgent(llm_client=client).chat("s-degrade", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")

    assert_common_shape(response)
    assert response["llm_used"] is False
    assert "当前结论围绕" in response["answer"]


def test_high_risk_llm_answer_keeps_safety_prerequisites(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([RetrievedDoc(DOC, 2.5, {})]))

    response = WindOpsAgent(llm_client=StubLLM("直接打开柜门检查即可。" )).chat(
        "s-risk", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？"
    )

    assert_common_shape(response)
    assert response["llm_used"] is True
    assert response["risk_level"] == "high"
    assert "停机" in response["answer"] and "断电" in response["answer"]
    assert any("停机" in item for item in response["follow_up_questions"])
    assert any("断电" in item or "挂牌" in item for item in response["follow_up_questions"])


def test_two_sessions_memory_is_isolated(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "retriever", SpyRetriever([RetrievedDoc(DOC, 2.5, {})]))
    agent = WindOpsAgent(llm_client=StubLLM())

    agent.chat("session-a", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")
    agent.chat("session-b", "系统在吗")

    memory_a = memory_store.get("session-a")
    memory_b = memory_store.get("session-b")
    assert len(memory_a["history"]) == 2
    assert len(memory_b["history"]) == 2
    assert memory_a["history"][-1]["intent"] != memory_b["history"][-1]["intent"]
    assert all(item.session_id == "session-a" for item in memory_store._milvus_like[:2])
    assert all(item.session_id == "session-b" for item in memory_store._milvus_like[2:])
