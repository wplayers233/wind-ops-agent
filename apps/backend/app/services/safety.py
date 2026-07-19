from __future__ import annotations

from typing import Any


HIGH_RISK_TERMS = ["停机", "断电", "挂牌", "过压", "过载", "高压", "中断", "爬塔", "登塔", "带电"]


def assess_safety(query: str, best: dict | list[dict] | None = None) -> dict[str, Any]:
    if isinstance(best, list):
        evidence = best
        best_doc = evidence[0] if evidence else {}
    else:
        evidence = [best] if best else []
        best_doc = best or {}
    high_risk = any(term in (query or "") for term in HIGH_RISK_TERMS) or any(item.get("safety_level") == "high" for item in evidence)
    risk_level = "high" if high_risk else "medium"
    notice = "高风险作业需由具备资质人员确认停机、断电、挂牌，并遵守现场规程。" if high_risk else "排查时请做好监护并记录现场参数。"
    return {
        "risk_level": risk_level,
        "notice": notice,
        "needs_confirmation": high_risk,
        "follow_up_questions": ["是否已确认停机状态？", "现场是否已断电并挂牌？"] if high_risk else ["是否有更多现场现象？"],
        "candidate_causes": [],
        "repair_steps": [],
        "tools": [],
        "spare_parts": [],
        "evidence_title": best_doc.get("title", ""),
    }
