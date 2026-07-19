from __future__ import annotations

from typing import Any, TypedDict


class WindOpsState(TypedDict, total=False):
    session_id: str
    query: str
    intent: dict[str, Any]
    intent_analysis: dict[str, Any]
    memory: dict[str, Any]
    route: str
    missing_slots: list[str]
    evidence: list[dict[str, Any]]
    retrieval_trace: dict[str, Any]
    diagnosis_result: dict[str, Any]
    safety_result: dict[str, Any]
    safety_confirmed: bool
    ticket_summary: str
    answer: str
    follow_up_questions: list[str]
    confidence: float
    risk_level: str
    safety_notice: str
    llm_used: bool
    errors: list[str]
    status: str
    awaiting_confirmation: bool
    input_persisted: bool

