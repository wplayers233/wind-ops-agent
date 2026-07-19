from app.services.agent import WindOpsAgent
from app.services.memory import memory_store


def setup_function() -> None:
    memory_store._redis_like.clear()
    memory_store._milvus_like.clear()


def test_quality_gate_scenario_a_explicit_pitch_fault() -> None:
    response = WindOpsAgent().chat("e2e-a", "2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？")

    assert response["intent"]["name"] == "fault_diagnosis"
    assert response["evidence"]
    assert response["evidence"][0]["component"] == "变桨系统"
    assert response["evidence"][0]["alarm_code"] == "PITCH_COMM_LOST"
    assert response["risk_level"] == "high"
    assert response["diagnosis_result"]["candidate_causes"]
    assert response["diagnosis_result"]["repair_steps"]
    assert response["diagnosis_result"]["citations"]
    assert response["safety_notice"]


def test_quality_gate_scenario_b_followup_inherits_session_context_only() -> None:
    agent = WindOpsAgent()
    first = agent.chat("e2e-b", "2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？")
    second = agent.chat("e2e-b", "这个怎么处理")
    isolated = agent.chat("e2e-b-isolated", "这个怎么处理")

    assert first["evidence"] and first["evidence"][0]["component"] == "变流器"
    assert second["intent_analysis"]["asset"]["component"] == "变流器"
    assert second["risk_level"] == "high"
    assert any("停机" in item or "断电" in item or "挂牌" in item for item in second["follow_up_questions"])
    assert isolated["intent_analysis"]["asset"]["component"] != "变流器"


def test_quality_gate_scenario_c_ticket_needs_more_info_without_fake_citation() -> None:
    response = WindOpsAgent().chat("e2e-c", "帮我生成工单")

    assert response["intent"]["name"] == "ticket_create"
    assert response["evidence"] == []
    assert response["follow_up_questions"]
    assert any("设备" in item or "现象" in item or "报警" in item for item in response["follow_up_questions"])
    assert response["diagnosis_result"]["citations"] == []
