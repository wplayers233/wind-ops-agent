from app.services.answer_planner import AnswerPlanner


BEST = {
    "title": "变流器过压故障手册",
    "source": "converter_manual.pdf",
    "page": 8,
    "component": "变流器",
    "symptoms": ["直流母线过压", "跳闸停机", "直流母线过压"],
    "causes": ["电网电压波动", "制动单元异常", "电网电压波动"],
    "steps": ["核对母线电压记录", "检查制动单元状态", "核对母线电压记录"],
}


def test_high_risk_answer_starts_with_safety_conditions() -> None:
    answer = AnswerPlanner().compose_answer("变流器过压跳闸怎么处理？", BEST, {"risk_level": "high"})

    assert answer.startswith("当前问题属于高风险场景，请先确认人员资质、停机、断电、挂牌和现场规程要求")
    assert "禁止直接拆卸、更换或带电测量" in answer
    assert "初步定位部件为变流器" in answer
    assert "依据：变流器过压故障手册（converter_manual.pdf 第8页）" in answer


def test_ticket_answer_contains_symptom_component_risk_and_evidence() -> None:
    answer = AnswerPlanner().compose_ticket_answer("变流器过压跳闸", BEST, {"risk_level": "high"})

    assert "故障现象为变流器过压跳闸" in answer
    assert "初判部件为变流器" in answer
    assert "风险等级为high" in answer
    assert "依据为变流器过压故障手册（converter_manual.pdf 第8页）" in answer
    assert "人员资质" in answer


def test_answer_deduplicates_repeated_facts() -> None:
    answer = AnswerPlanner().compose_answer("变流器过压跳闸怎么处理？", BEST, {"risk_level": "medium"})

    assert answer.count("直流母线过压") == 1
    assert answer.count("电网电压波动") == 1
    assert answer.count("核对母线电压记录") == 1
