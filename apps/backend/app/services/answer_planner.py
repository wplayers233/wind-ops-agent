from __future__ import annotations


class AnswerPlanner:
    def fallback_answer(self, intent_name: str) -> str:
        if intent_name == "llm_fallback":
            return "当前意图不够明确，已进入检索兜底流程，请补充设备型号、报警码或现场现象。"
        return "未检索到足够证据，请补充设备型号、报警码或现场现象。"

    def compose_answer(self, query: str, best: dict, safety: dict | None = None) -> str:
        steps = _unique_text(best.get("steps", []))[:4]
        causes = _unique_text(best.get("causes", []))[:3]
        symptoms = _unique_text(best.get("symptoms", []))[:3]
        component = best.get("component") or "相关部件"
        source = _source_text(best)
        body = (f"当前结论围绕“{query}”。初步定位部件为{component}。"
                f"典型现象包括{_join_or_placeholder(symptoms, '证据未明确描述')}。"
                f"可能原因包括{_join_or_placeholder(causes, '证据不足')}。"
                f"建议步骤：{_join_or_placeholder(steps, '先补充设备型号、报警码或现场现象')}。"
                f"依据：{source}。")
        if (safety or {}).get("risk_level") == "high":
            return "当前问题属于高风险场景，请先确认人员资质、停机、断电、挂牌和现场规程要求。禁止直接拆卸、更换或带电测量。" + body
        return body

    def compose_ticket_answer(self, query: str, best: dict, safety: dict) -> str:
        component = best.get("component") or "相关部件"
        source = _source_text(best)
        risk_level = safety.get("risk_level", "unknown")
        safety_prefix = "高风险工单需先确认人员资质、停机、断电、挂牌和现场规程要求。" if risk_level == "high" else ""
        return f"已按工单意图整理：故障现象为{query}，初判部件为{component}，风险等级为{risk_level}，依据为{source}。{safety_prefix}".strip()


def _unique_text(values: list[object]) -> list[str]:
    result: list[str] = []
    seen = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _join_or_placeholder(values: list[str], placeholder: str) -> str:
    return "、".join(values) if values else placeholder


def _source_text(best: dict) -> str:
    title = best.get("title") or "未命名证据"
    source = best.get("source") or "未知来源"
    page = best.get("page") or 0
    return f"{title}（{source} 第{page}页）"