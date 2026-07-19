import json

from app.services.diagnosis import build_diagnosis_result
from app.services.safety import assess_safety


PITCH_EVIDENCE = [
    {
        "title": "2.5MW 变桨通讯故障排查手册",
        "source": "pitch_manual.pdf",
        "page": 12,
        "score": 0.91,
        "system": "变桨系统",
        "component": "变桨控制器",
        "fault_domain": "通讯中断",
        "alarm_code": "PITCH_COMM_LOST",
        "causes": ["滑环通讯链路松动", "变桨控制器供电异常", "滑环通讯链路松动"],
        "steps": ["检查滑环通讯接头是否松动", "读取变桨控制器供电电压", "检查滑环通讯接头是否松动"],
        "tools": ["万用表", "通讯诊断仪", "万用表"],
        "spare_parts": ["通讯接头", "变桨控制器", "通讯接头"],
        "safety_level": "medium",
    },
    {
        "title": "变桨维护记录",
        "source": "work_order.csv",
        "page": 2,
        "score": 0.77,
        "system": "变桨系统",
        "component": "变桨控制器",
        "fault_domain": "通讯中断",
        "alarm_code": "PITCH_COMM_LOST",
        "causes": ["轮毂通讯干扰"],
        "steps": ["检查轮毂通讯屏蔽层接地", "读取变桨控制器供电电压"],
        "tools": ["绝缘手套"],
        "spare_parts": ["屏蔽线"],
        "safety_level": "low",
    },
]


def _intent(asset: dict | None = None, slots: dict | None = None) -> dict:
    return {"asset": asset or {}, "slots": slots or {"missing_slots": [], "blocking_missing_slots": []}}


def test_pitch_communication_evidence_builds_structured_diagnosis() -> None:
    safety = assess_safety("2.5MW 变桨通讯中断，报 PITCH_COMM_LOST", PITCH_EVIDENCE)
    result = build_diagnosis_result("2.5MW 变桨通讯中断，报 PITCH_COMM_LOST", _intent(), PITCH_EVIDENCE, safety)

    assert result["system"] == "变桨系统"
    assert result["component"] == "变桨控制器"
    assert result["fault_domain"] == "通讯中断"
    assert result["alarm_code"] == "PITCH_COMM_LOST"
    assert result["candidate_causes"]
    assert result["repair_steps"]
    assert "万用表" in result["tools"]
    assert "通讯接头" in result["spare_parts"]
    assert result["citations"][0]["title"] == "2.5MW 变桨通讯故障排查手册"
    json.dumps(result, ensure_ascii=False)


def test_no_evidence_keeps_complete_structure_and_empty_citations() -> None:
    safety = assess_safety("未知故障", [])
    result = build_diagnosis_result("未知故障", _intent(), [], safety)

    expected_keys = {
        "summary",
        "system",
        "component",
        "fault_domain",
        "alarm_code",
        "candidate_causes",
        "repair_steps",
        "tools",
        "spare_parts",
        "risk_level",
        "safety_warnings",
        "citations",
        "missing_slots",
        "next_action",
    }
    assert set(result) == expected_keys
    assert result["citations"] == []
    assert result["candidate_causes"] == []
    assert result["repair_steps"] == []
    json.dumps(result, ensure_ascii=False)


def test_duplicate_causes_steps_tools_and_spares_are_deduplicated() -> None:
    result = build_diagnosis_result("变桨通讯中断", _intent(), PITCH_EVIDENCE, assess_safety("变桨通讯中断", PITCH_EVIDENCE))

    causes = [item["cause"] for item in result["candidate_causes"]]
    step_actions = [item["action"] for item in result["repair_steps"]]
    assert len(causes) == len(set(causes))
    assert len(step_actions) == len(set(step_actions))
    assert len(result["tools"]) == len(set(result["tools"]))
    assert len(result["spare_parts"]) == len(set(result["spare_parts"]))


def test_step_numbers_are_continuous() -> None:
    result = build_diagnosis_result("变桨通讯中断", _intent(), PITCH_EVIDENCE, assess_safety("变桨通讯中断", PITCH_EVIDENCE))

    assert [item["step"] for item in result["repair_steps"]] == list(range(1, len(result["repair_steps"]) + 1))


def test_intent_asset_has_priority_over_evidence_asset() -> None:
    result = build_diagnosis_result(
        "通讯异常",
        _intent(asset={"system": "主控系统", "component": "主控PLC", "fault_domain": "通讯异常"}),
        PITCH_EVIDENCE,
        assess_safety("通讯异常", PITCH_EVIDENCE),
    )

    assert result["system"] == "主控系统"
    assert result["component"] == "主控PLC"
    assert result["fault_domain"] == "通讯异常"
