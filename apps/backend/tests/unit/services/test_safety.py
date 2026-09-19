from app.services.safety import assess_safety


def test_converter_over_voltage_is_high_risk() -> None:
    result = assess_safety("变流器过压跳闸，是否可以复位？", [])

    assert result["risk_level"] == "high"
    assert "资质" in result["notice"]
    assert "停机" in result["notice"]
    assert "断电" in result["notice"]
    assert "挂牌" in result["notice"]


def test_high_risk_evidence_upgrades_risk() -> None:
    result = assess_safety("柜内温度异常", [{"title": "高压柜维护手册", "safety_level": "high"}])

    assert result["risk_level"] == "high"


def test_medium_terms_are_at_least_medium() -> None:
    result = assess_safety("齿轮箱振动过温告警", [])

    assert result["risk_level"] == "medium"


def test_high_risk_query_without_evidence_does_not_drop_to_low() -> None:
    result = assess_safety("需要爬塔检查制动系统", [])

    assert result["risk_level"] == "high"
    assert result["needs_confirmation"] is True


def test_rank_two_high_risk_evidence_triggers_gate() -> None:
    result = assess_safety("柜内温度异常", [{"title": "清洁保养手册", "safety_level": "low"}, {"title": "高压柜维护手册", "safety_level": "high"}])

    assert result["risk_level"] == "high"
    assert result["needs_confirmation"] is True


def test_safety_tool_consumes_full_evidence_list() -> None:
    from app.services.tools import assess_safety_tool

    result = assess_safety_tool.invoke({"query": "柜内温度异常", "evidence": [{"title": "清洁保养手册", "safety_level": "low"}, {"title": "高压柜维护手册", "safety_level": "high"}]})

    assert result["risk_level"] == "high"
