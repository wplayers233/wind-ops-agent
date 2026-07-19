from dataclasses import asdict

from app.services.intent_router import IntentRouter


def test_ticket_create_routes_to_ticket_workflow() -> None:
    router = IntentRouter()
    result = router.route("我要报修并生成工单", {})
    assert result.intent == "ticket_create"
    assert result.task.name == "ticket_create"
    assert result.route.workflow == "ticket_workflow"


def test_health_check_synonym_has_high_priority() -> None:
    router = IntentRouter()
    result = router.route("系统在吗", {})
    assert result.intent == "health_check"
    assert result.confidence >= 0.8
    assert result.route.workflow == "health_workflow"


def test_safety_rule_beats_general_retrieval_rule() -> None:
    router = IntentRouter()
    result = router.route("查一下安全风险和挂牌要求", {})
    assert result.intent == "safety_check"
    assert result.asset.fault_domain == "electrical_risk"
    assert result.route.workflow == "safety_workflow"


def test_retrieval_rule_can_match_patterns() -> None:
    router = IntentRouter()
    result = router.route("查一下变桨系统手册资料", {})
    assert result.intent == "document_retrieval"
    assert result.route.workflow == "retrieval_workflow"


def test_retrieval_rule_can_match_terms() -> None:
    router = IntentRouter()
    result = router.route("帮我找一下资料", {})
    assert result.intent == "document_retrieval"


def test_fault_diagnosis_extracts_three_layers() -> None:
    router = IntentRouter()
    result = router.route("2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？", {})
    assert result.task.name == "fault_diagnosis"
    assert result.asset.system == "pitch_system"
    assert result.asset.component == "变桨系统"
    assert result.asset.fault_domain == "communication_fault"
    assert result.slots.model == "2.5MW"
    assert result.slots.alarm_code == "PITCH_COMM_LOST"
    assert result.route.workflow == "diagnosis_workflow"
    assert not result.route.need_clarification
    assert result.route.retrieval_filters["system"] == "pitch_system"


def test_converter_alarm_extracts_alarm_code_and_domain() -> None:
    router = IntentRouter()
    result = router.route("2.5MW 变流器直流母线过压，报 CONV_DC_OV 怎么处理？", {})
    assert result.task.name in {"fault_diagnosis", "repair_guidance"}
    assert result.asset.system == "converter_system"
    assert result.asset.component == "变流器"
    assert result.asset.fault_domain == "over_voltage"
    assert result.slots.alarm_code == "CONV_DC_OV"
    assert result.route.workflow == "diagnosis_workflow"


def test_context_followup_uses_last_component() -> None:
    router = IntentRouter()
    memory_state = {"history": [{"component": "变桨系统", "intent": "document_retrieval"}]}
    result = router.route("这个怎么处理", memory_state)
    assert result.asset.component == "变桨系统"
    assert "变桨系统" in result.reason


def test_context_does_not_override_clear_rule_match() -> None:
    router = IntentRouter()
    memory_state = {"history": [{"component": "变桨系统", "intent": "document_retrieval"}]}
    result = router.route("我要报修", memory_state)
    assert result.intent == "ticket_create"


def test_unknown_query_falls_back_when_no_context() -> None:
    router = IntentRouter()
    result = router.route("随便说点什么", {"history": []})
    assert result.intent == "llm_fallback"
    assert result.task.confidence == 0.4
    assert result.route.workflow == "fallback_workflow"


def test_empty_query_falls_back_when_no_context() -> None:
    router = IntentRouter()
    result = router.route("   ", {"history": []})
    assert result.intent == "llm_fallback"


def test_continue_question_reuses_history_component() -> None:
    router = IntentRouter()
    memory_state = {"history": [{"component": "变流器", "intent": "fault_diagnosis"}]}
    result = router.route("这个怎么处理", memory_state)
    assert result.asset.component == "变流器"
    assert result.route.workflow in {"diagnosis_workflow", "repair_workflow"}


def test_clear_rule_still_wins_over_history_on_safety_query() -> None:
    router = IntentRouter()
    memory_state = {"history": [{"component": "变桨系统", "intent": "document_retrieval"}]}
    result = router.route("高空作业要注意什么安全风险", memory_state)
    assert result.intent == "safety_check"
    assert result.route.workflow == "safety_workflow"
    assert result.asset.component != "变桨系统"


def test_mandatory_matrix_safety_query_routes_to_safety_workflow() -> None:
    router = IntentRouter()
    result = router.route("高空作业要注意什么风险", {})
    assert result.task.name == "safety_check"
    assert result.route.workflow == "safety_workflow"


def test_mandatory_matrix_ticket_create_asks_when_insufficient() -> None:
    router = IntentRouter()
    result = router.route("帮我生成维修工单", {})
    assert result.task.name == "ticket_create"
    assert result.route.workflow == "ticket_workflow"
    assert result.route.need_clarification
    assert result.route.clarification_questions


def test_mandatory_matrix_diagram_lookup_has_yaw_filter() -> None:
    router = IntentRouter()
    result = router.route("找偏航接线图", {})
    assert result.task.name == "diagram_lookup"
    assert result.route.workflow == "diagram_workflow"
    assert result.route.retrieval_filters["system"] == "yaw_system"
    assert result.route.retrieval_filters["component"] == "偏航系统"


def test_analysis_is_dataclass_serializable_and_filters_have_no_empty_values() -> None:
    router = IntentRouter()
    result = router.route("2.5MW 变桨报 PITCH_COMM_LOST 怎么排查", {})
    serialized = asdict(result)
    assert serialized["task"]["name"] == "fault_diagnosis"
    assert all(value not in (None, "", []) for value in result.route.retrieval_filters.values())


def test_high_risk_safety_missing_status_needs_clarification() -> None:
    router = IntentRouter()
    result = router.route("高压柜能不能带电检查", {})
    assert result.task.name == "safety_check"
    assert result.route.workflow == "safety_workflow"
    assert result.route.need_clarification
    assert "operation_status" in result.slots.blocking_missing_slots

