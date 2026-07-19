from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from types import SimpleNamespace

from app.services.graph import GraphRunner
from app.services.retriever import retriever

COMMON_RESPONSE_KEYS = {
    "session_id", "query", "answer", "intent", "intent_analysis", "diagnosis_result", "confidence", "risk_level", "safety_notice", "evidence", "retrieval_trace", "ticket_summary", "follow_up_questions", "memory_summary", "llm_used",
}

VISIBLE_RESPONSE_KEYS = {
    "session_id",
    "query",
    "answer",
    "intent",
    "intent_analysis",
    "diagnosis_result",
    "confidence",
    "risk_level",
    "safety_notice",
    "evidence",
    "retrieval_trace",
    "ticket_summary",
    "follow_up_questions",
    "memory_summary",
    "llm_used",
}


@dataclass
class WindOpsAgent:
    runner: GraphRunner | None = None
    llm_client: Any | None = None

    def __post_init__(self) -> None:
        if self.runner is None:
            # Inject the legacy dependencies into the graph so existing callers and tests remain isolated.
            legacy_mode = self.llm_client is not None
            self.runner = GraphRunner(
                retriever_obj=retriever,
                model=self.llm_client if legacy_mode else None,
                auto_confirm_high_risk=legacy_mode,
            )
        self.llm_client = self.llm_client or SimpleNamespace(api_key=None)

    def chat(self, session_id: str, query: str) -> dict[str, Any]:
        state = self.runner.invoke(session_id, query)
        return self._response(session_id, query, state)

    def resume(self, session_id: str, confirmed: bool) -> dict[str, Any]:
        state = self.runner.resume(session_id, confirmed)
        query = state.get("query", "")
        return self._response(session_id, query, state)

    def _response(self, session_id: str, query: str, state: dict[str, Any]) -> dict[str, Any]:
        interrupts = state.get("__interrupt__") or []
        if interrupts:
            request = interrupts[0].value if hasattr(interrupts[0], "value") else {}
            response = {
                "session_id": session_id,
                "query": query,
                "answer": "当前问题涉及高风险操作，请先确认安全条件后继续。",
                "intent": state.get("intent", {}),
                "intent_analysis": state.get("intent_analysis", {}),
                "diagnosis_result": state.get("diagnosis_result", {"candidate_causes": [], "repair_steps": [], "citations": []}),
                "confidence": state.get("confidence", 0.0),
                "risk_level": "high",
                "safety_notice": state.get("safety_notice", "必须确认停机、断电、挂牌和人员资质。"),
                "evidence": state.get("evidence", []),
                "retrieval_trace": state.get("retrieval_trace", {}),
                "ticket_summary": "",
                "follow_up_questions": request.get("questions", []),
                "memory_summary": state.get("memory", {}).get("summary", ""),
                "llm_used": False,
                "status": "awaiting_confirmation",
                "interrupt": request,
            }
        else:
            response = {
                "session_id": session_id,
                "query": query,
                "answer": state.get("answer", ""),
                "intent": state.get("intent", {}),
                "intent_analysis": state.get("intent_analysis", {}),
                "diagnosis_result": state.get("diagnosis_result", {"candidate_causes": [], "repair_steps": [], "citations": []}),
                "confidence": float(state.get("confidence", 0.0)),
                "risk_level": state.get("risk_level", "unknown"),
                "safety_notice": state.get("safety_notice", ""),
                "evidence": state.get("evidence", []),
                "retrieval_trace": state.get("retrieval_trace", {}),
                "ticket_summary": state.get("ticket_summary", ""),
                "follow_up_questions": state.get("follow_up_questions", []),
                "memory_summary": state.get("memory", {}).get("summary", ""),
                "llm_used": bool(state.get("llm_used", False)),
            }
            if self.runner.include_status:
                response["status"] = state.get("status", "completed")

        for key in list(response.keys()):
            if key not in VISIBLE_RESPONSE_KEYS and key != "status":
                response.pop(key, None)
        return response


agent = WindOpsAgent()




