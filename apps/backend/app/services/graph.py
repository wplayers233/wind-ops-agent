from __future__ import annotations

from dataclasses import asdict
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.services.agent_state import WindOpsState
from app.services.answer_planner import AnswerPlanner
from app.services.diagnosis import build_diagnosis_result, validate_diagnosis_output
from app.services.intent_router import IntentRouter
from app.services.memory import memory_store
from app.services.model_factory import build_chat_model, model_mode
from app.services.retriever import retriever
from app.services.safety import assess_safety
from app.services.tools import (
    assess_safety_tool,
    build_diagnosis_tool,
    build_ticket_tool,
    retrieve_keyword,
    retrieve_with_retriever,
)

HIGH_RISK_QUESTIONS = ["是否已确认停机状态？", "现场是否已断电并挂牌？"]


class ResumeNotAvailableError(Exception):
    """Raised when a session has no pending safety confirmation to resume."""


def _analysis_dict(analysis: Any) -> dict[str, Any]:
    return asdict(analysis) if hasattr(analysis, "__dataclass_fields__") else dict(analysis or {})


def _intent_dict(analysis: Any) -> dict[str, Any]:
    return {"name": analysis.task.name, "confidence": analysis.confidence, "reason": analysis.reason}


def _llm_text(model: Any, state: WindOpsState) -> str | None:
    """Adapt legacy generate clients and LangChain chat models to one boundary."""
    if model is None:
        return None
    payload = {
        "query": state.get("query", ""),
        "intent": state.get("intent_analysis", {}),
        "diagnosis_result": state.get("diagnosis_result", {}),
        "safety": state.get("safety_result", {}),
    }
    try:
        if hasattr(model, "generate"):
            value = model.generate(**payload)
        elif hasattr(model, "invoke"):
            value = model.invoke(
                [
                    ("system", "你是风电运维助手。只能依据给定证据回答，不得覆盖安全规则或编造引用。"),
                    ("human", str(payload)),
                ]
            )
        else:
            return None
    except Exception:
        return None
    content = getattr(value, "content", value)
    if isinstance(content, list):
        content = "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    if not isinstance(content, str) or not content.strip():
        return None
    return content.strip()


def _with_safety_prefix(answer: str, state: WindOpsState) -> str:
    if state.get("risk_level") != "high":
        return answer
    required = "停机、断电、挂牌"
    if all(term in answer for term in ("停机", "断电", "挂牌")):
        return answer
    notice = state.get("safety_notice") or "必须确认停机、断电、挂牌和人员资质。"
    return f"安全前置条件：{notice}\n{answer}"


def _strip_internal_metadata(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\\n", "\n").splitlines()]
    blocked = ("置信度", "confidence", "score", "LLM", "llm", "debug", "metadata")
    kept = [line for line in lines if line and not any(token.lower() in line.lower() for token in blocked)]
    return "\n".join(kept).strip()


def build_graph(
    retriever_obj: Any | None = None,
    memory_store_obj: Any | None = None,
    model: Any | None = None,
    auto_confirm_high_risk: bool = False,
):
    """Build an isolated graph so tests and deployments can inject providers."""
    searcher = retriever_obj or retriever
    memories = memory_store_obj or memory_store
    answer_planner = AnswerPlanner()

    def supervisor(state: WindOpsState) -> dict[str, Any]:
        router = IntentRouter()
        memory = memories.get(state["session_id"])
        analysis = router.analyze(state["query"], memory)
        # Persist the input before a possible interrupt so resume retains context.
        memories.update(
            state["session_id"],
            {
                "role": "user",
                "content": state["query"],
                "component": analysis.asset.component or "",
                "intent": analysis.task.name,
            },
        )
        return {
            "memory": memories.get(state["session_id"]),
            "intent": _intent_dict(analysis),
            "intent_analysis": _analysis_dict(analysis),
            "route": analysis.route.workflow,
            "missing_slots": list(analysis.slots.missing_slots),
            "status": "routed",
            "llm_used": False,
            "input_persisted": True,
        }

    def greeting(state: WindOpsState) -> dict[str, Any]:
        return {
            "answer": "你好，我是 WindRAG 风电运维助手。你可以输入机型、报警码和现场现象，我会检索运维资料并给出带引用的排查建议。",
            "follow_up_questions": ["请描述故障现象", "请补充报警码"],
            "status": "completed",
            "risk_level": "unknown",
            "safety_notice": "",
            "diagnosis_result": {"candidate_causes": [], "repair_steps": [], "citations": []},
            "evidence": [],
            "retrieval_trace": {"count": 0, "graph_node": "greeting"},
            "ticket_summary": "",
            "confidence": state.get("intent", {}).get("confidence", 0.9),
        }

    def clarification(state: WindOpsState) -> dict[str, Any]:
        questions = [
            "请补充具体设备部件或系统，例如变桨系统、齿轮箱、变流器。",
            "请补充具体现象或报警信息，例如通讯中断、油温过高、母线过压。",
        ]
        return {
            "answer": "当前信息不足，暂不生成确定性诊断。请先补充关键运维信息。",
            "follow_up_questions": questions,
            "status": "needs_clarification",
            "risk_level": "unknown",
            "safety_notice": "",
            "diagnosis_result": {"candidate_causes": [], "repair_steps": [], "citations": []},
            "evidence": [],
            "retrieval_trace": {"count": 0, "graph_node": "clarification"},
            "ticket_summary": "",
            "confidence": min(0.6, state.get("intent", {}).get("confidence", 0.4)),
        }

    def retrieval(state: WindOpsState) -> dict[str, Any]:
        analysis = state.get("intent_analysis", {})
        route = analysis.get("route", {})
        if searcher is retriever:
            result = retrieve_keyword.invoke({"query": state["query"], "filters": route.get("retrieval_filters", {})})
        else:
            result = retrieve_with_retriever(searcher, state["query"], route.get("retrieval_filters", {}))
        return {
            "evidence": result.get("evidence", []),
            "retrieval_trace": {**result.get("retrieval_trace", {}), "graph_node": "retrieval_agent"},
            "status": "retrieved",
        }

    def safety(state: WindOpsState) -> dict[str, Any]:
        if searcher is retriever:
            result = assess_safety_tool.invoke({"query": state["query"], "evidence": state.get("evidence", [])})
        else:
            evidence = state.get("evidence", [])
            result = assess_safety(state["query"], evidence[0] if evidence else {})
        return {
            "safety_result": result,
            "risk_level": result.get("risk_level", "unknown"),
            "safety_notice": result.get("notice", ""),
            "follow_up_questions": result.get("follow_up_questions", []),
        }

    def diagnosis(state: WindOpsState) -> dict[str, Any]:
        evidence = state.get("evidence", [])
        safety_result = state.get("safety_result", {})
        if searcher is retriever:
            result = build_diagnosis_tool.invoke(
                {
                    "query": state["query"],
                    "intent_analysis": state.get("intent_analysis", {}),
                    "evidence": evidence,
                    "safety": safety_result,
                }
            )
        else:
            result = build_diagnosis_result(state["query"], state.get("intent_analysis", {}), evidence, safety_result)
        try:
            result = validate_diagnosis_output(result)
        except Exception as exc:
            # Keep the graph available even when an external provider returns a malformed payload.
            result = {**result, "status": "invalid_structured_output", "validation_error": str(exc)}
        if not evidence:
            result["status"] = "insufficient_evidence"
        return {"diagnosis_result": result, "status": "diagnosed" if evidence else "insufficient_evidence"}

    def safety_gate(state: WindOpsState) -> dict[str, Any]:
        if state.get("risk_level") != "high" or state.get("safety_confirmed") or auto_confirm_high_risk:
            return {"awaiting_confirmation": False}
        decision = interrupt(
            {
                "type": "safety_confirmation_required",
                "questions": HIGH_RISK_QUESTIONS,
                "session_id": state["session_id"],
            }
        )
        confirmed = decision.get("confirmed", False) if isinstance(decision, dict) else bool(decision)
        if not confirmed:
            return {
                "awaiting_confirmation": False,
                "status": "safety_blocked",
                "answer": "安全条件未确认，暂不生成可执行排查建议。",
                "follow_up_questions": HIGH_RISK_QUESTIONS,
            }
        return {"safety_confirmed": True, "awaiting_confirmation": False, "status": "safety_confirmed"}

    def ticket(state: WindOpsState) -> dict[str, Any]:
        summary = build_ticket_tool.invoke(
            {
                "query": state["query"],
                "evidence": state.get("evidence", []),
                "safety": state.get("safety_result", {}),
            }
        )
        return {"ticket_summary": summary}

    def answer(state: WindOpsState) -> dict[str, Any]:
        if state.get("answer") and state.get("status") in {"safety_blocked", "needs_clarification", "completed"}:
            response = state["answer"]
            used_model = False
        else:
            response = _llm_text(model, state)
            used_model = bool(response)
            if not response:
                if not state.get("evidence"):
                    response = answer_planner.fallback_answer(state.get("intent", {}).get("name", ""))
                else:
                    response = answer_planner.compose_answer(state["query"], state["evidence"][0], state.get("safety_result", {}))
        response = _strip_internal_metadata(_with_safety_prefix(response, state))
        return {"answer": response, "status": "completed", "llm_used": used_model}

    def memory_write(state: WindOpsState) -> dict[str, Any]:
        if not state.get("input_persisted"):
            memories.update(
                state["session_id"],
                {
                    "role": "user",
                    "content": state["query"],
                    "component": state.get("diagnosis_result", {}).get("component", ""),
                    "intent": state.get("intent", {}).get("name", ""),
                },
            )
        memories.update(
            state["session_id"],
            {
                "role": "assistant",
                "content": state.get("answer", ""),
                "component": state.get("diagnosis_result", {}).get("component", ""),
                "intent": state.get("intent", {}).get("name", ""),
            },
        )
        return {"memory": memories.get(state["session_id"]), "status": state.get("status", "completed")}

    def after_supervisor(state: WindOpsState) -> str:
        name = state.get("intent", {}).get("name")
        if name == "health_check":
            return "greeting"
        analysis = state.get("intent_analysis", {})
        route = analysis.get("route", {})
        if name == "llm_fallback" or route.get("need_clarification"):
            return "clarification"
        # A repair request without an object is not actionable enough to retrieve.
        generic_symptoms = {"排查", "故障", "报警", "异常", "风险", "原因"}
        if name in {"repair_guidance", "fault_diagnosis"} and not analysis.get("asset", {}).get("component") and analysis.get("slots", {}).get("symptom") in generic_symptoms:
            return "clarification"
        return "retrieval"

    def after_safety_gate(state: WindOpsState) -> str:
        return "answer" if state.get("status") == "safety_blocked" else "ticket"

    graph = StateGraph(WindOpsState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("greeting", greeting)
    graph.add_node("clarification", clarification)
    graph.add_node("retrieval", retrieval)
    graph.add_node("safety", safety)
    graph.add_node("diagnosis", diagnosis)
    graph.add_node("safety_gate", safety_gate)
    graph.add_node("ticket", ticket)
    graph.add_node("answer", answer)
    graph.add_node("memory_write", memory_write)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", after_supervisor, {"greeting": "greeting", "clarification": "clarification", "retrieval": "retrieval"})
    graph.add_edge("greeting", "memory_write")
    graph.add_edge("clarification", "memory_write")
    graph.add_edge("retrieval", "safety")
    graph.add_edge("safety", "diagnosis")
    graph.add_edge("diagnosis", "safety_gate")
    graph.add_conditional_edges("safety_gate", after_safety_gate, {"answer": "answer", "ticket": "ticket"})
    graph.add_edge("ticket", "answer")
    graph.add_edge("answer", "memory_write")
    graph.add_edge("memory_write", END)
    return graph.compile(checkpointer=MemorySaver())


class GraphRunner:
    def __init__(
        self,
        retriever_obj: Any | None = None,
        memory_store_obj: Any | None = None,
        model: Any | None = None,
        auto_confirm_high_risk: bool = False,
    ) -> None:
        self.retriever = retriever_obj or retriever
        self.memory_store = memory_store_obj or memory_store
        self.model = model if model is not None else build_chat_model()
        self.model_mode = model_mode(self.model)
        self.include_status = not auto_confirm_high_risk
        self.graph = build_graph(self.retriever, self.memory_store, self.model, auto_confirm_high_risk)

    def invoke(self, session_id: str, query: str) -> dict[str, Any]:
        return self.graph.invoke(
            {
                "session_id": session_id,
                "query": query,
                "safety_confirmed": False,
            },
            {"configurable": {"thread_id": session_id}},
        )

    def resume(self, session_id: str, confirmed: bool) -> dict[str, Any]:
        config = {"configurable": {"thread_id": session_id}}
        if not self.graph.get_state(config).next:
            raise ResumeNotAvailableError(f"会话 '{session_id}' 没有等待确认的高风险操作。")
        return self.graph.invoke(Command(resume={"confirmed": confirmed}), config)


runner = GraphRunner()
