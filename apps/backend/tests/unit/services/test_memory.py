from app.services.memory import MemoryStore


def test_memory_is_isolated_by_session() -> None:
    store = MemoryStore()
    store.update("s1", {"content": "变桨报警", "component": "变桨系统", "intent": "fault_diagnosis"})
    store.update("s2", {"content": "变流器报警", "component": "变流器", "intent": "fault_diagnosis"})

    assert store.get("s1")["history"][-1]["component"] == "变桨系统"
    assert store.get("s2")["history"][-1]["component"] == "变流器"
    assert all(item["component"] != "变流器" for item in store.search_long_memory("s1", "变流器 报警"))


def test_memory_limit_trims_short_history() -> None:
    store = MemoryStore(short_limit=3)
    for index in range(5):
        store.update("s1", {"content": f"第{index}轮", "component": "变桨系统", "intent": "fault_diagnosis"})

    state = store.get("s1")
    assert len(state["history"]) == 3
    assert state["history"][0]["content"] == "第2轮"


def test_memory_ttl_expires_without_waiting() -> None:
    store = MemoryStore(short_ttl_seconds=1)
    store.update("s1", {"content": "过期记录", "component": "齿轮箱", "created_at": 1.0})

    state = store.get("s1")
    assert state["history"] == []
    assert state["summary"] == ""


def test_memory_get_returns_safe_copy() -> None:
    store = MemoryStore()
    state = store.update("s1", {"content": "变桨报警", "component": "变桨系统"})
    state["history"][0]["component"] = "被外部篡改"

    assert store.get("s1")["history"][0]["component"] == "变桨系统"


def test_memory_summary_reflects_rounds_component_and_intent() -> None:
    store = MemoryStore()
    store.update("s1", {"content": "第一轮", "component": "变桨系统", "intent": "fault_diagnosis"})
    store.update("s1", {"content": "第二轮", "component": "变流器", "intent": "repair_guidance"})

    summary = store.get("s1")["summary"]
    assert "已累计2轮" in summary
    assert "变流器" in summary
    assert "repair_guidance" in summary


def test_long_memory_returns_only_same_session_records() -> None:
    store = MemoryStore()
    store.update("s1", {"content": "变桨通讯中断", "component": "变桨系统", "intent": "fault_diagnosis"})
    store.update("s2", {"content": "变桨通讯中断", "component": "变桨系统", "intent": "fault_diagnosis"})

    results = store.search_long_memory("s1", "变桨系统 通讯中断")
    assert results
    assert all(item["content"] == "变桨通讯中断" for item in results)
    assert len(results) == 1


def test_memory_reports_fallback_mode_and_persistence_status() -> None:
    store = MemoryStore()
    state = store.update("s-status", {"content": "变桨通讯中断", "component": "变桨系统"})
    assert state["memory_mode"] in {"memory_fallback", "redis+milvus"}
    assert state["persist_status"] == "queued"