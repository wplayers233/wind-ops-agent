from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.services.answer_planner import AnswerPlanner
from app.services.diagnosis import build_diagnosis_result
from app.services.retriever import retriever
from app.services.safety import assess_safety


@tool
def retrieve_keyword(query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieve evidence from the hybrid local index and return traceable documents."""
    return retrieve_with_retriever(retriever, query, filters)


def retrieve_with_retriever(retriever_obj: Any, query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the same LangChain tool contract against an injected retriever."""
    try:
        items = retriever_obj.retrieve(query, top_k=5, filters=filters or {})
    except TypeError:
        # Keep compatibility with minimal test adapters exposing the pre-top_k signature.
        items = retriever_obj.retrieve(query, filters or {})
    evidence = [item.doc for item in items]
    trace = {"count": len(evidence), "channels": [item.trace for item in items], "tool": "retrieve_keyword"}
    return {"evidence": evidence, "retrieval_trace": trace}


@tool
def assess_safety_tool(query: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess operational risk before any answer is generated."""
    return assess_safety(query, evidence)


@tool
def build_diagnosis_tool(query: str, intent_analysis: dict[str, Any], evidence: list[dict[str, Any]], safety: dict[str, Any]) -> dict[str, Any]:
    """Build a structured diagnosis grounded in retrieved evidence."""
    return build_diagnosis_result(query, intent_analysis, evidence, safety)


@tool
def build_ticket_tool(query: str, evidence: list[dict[str, Any]], safety: dict[str, Any]) -> str:
    """Build a ticket summary without inventing a citation."""
    if not evidence:
        return "知识库证据不足，建议补充报警码与机组信息后再生成工单。"
    best = evidence[0]
    return f"故障现象：{query}；初判部件：{best.get('component', '未知')}；风险等级：{safety.get('risk_level', 'unknown')}；建议依据：{best.get('title', '未知文档')}（{best.get('source', '未知来源')} 第{best.get('page', 0)}页）。"


answer_planner = AnswerPlanner()
