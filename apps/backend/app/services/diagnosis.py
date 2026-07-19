from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class CandidateCause(BaseModel):
    model_config = ConfigDict(extra="allow")

    cause: str
    confidence: float = Field(ge=0, le=1)
    evidence: str = ""
    check_method: str = ""


class RepairStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    step: int = Field(ge=1)
    action: str
    source: str = ""
    expected_result: str = ""
    risk: str = "low"


class Citation(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    source: str
    page: int = Field(ge=1)
    score: float = 0.0


class DiagnosisOutput(BaseModel):
    """Structured boundary for diagnosis nodes and optional LLM providers."""
    model_config = ConfigDict(extra="allow")

    summary: str = ""
    system: str = ""
    component: str = ""
    fault_domain: str = ""
    alarm_code: str = ""
    candidate_causes: list[CandidateCause] = Field(default_factory=list)
    repair_steps: list[RepairStep] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    spare_parts: list[str] = Field(default_factory=list)
    risk_level: str = "unknown"
    safety_warnings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    missing_slots: list[str] = Field(default_factory=list)
    next_action: str = ""


def validate_diagnosis_output(value: dict) -> dict:
    """Validate and normalize the diagnosis contract before answer generation."""
    return DiagnosisOutput.model_validate(value).model_dump()

MAX_CITATIONS = 3
MAX_STEPS = 6
MAX_ITEMS = 8


def build_diagnosis_result(query: str, intent_analysis: dict, evidence: list[dict], safety: dict | None) -> dict:
    best = evidence[0] if evidence else {}
    causes = _rank_causes(query, evidence)
    steps = _build_repair_steps(evidence)
    tools = _unique_from_evidence(evidence, "tools")
    spare_parts = _unique_from_evidence(evidence, "spare_parts")
    citations = _build_citations(evidence)
    asset = intent_analysis.get("asset", {}) or {}
    slots = intent_analysis.get("slots", {}) or {}
    risk_level = (safety or {}).get("risk_level", "unknown")

    return {
        "summary": _summary(query, best, asset, evidence),
        "system": _first_present(asset.get("system"), best.get("system")),
        "component": _first_present(asset.get("component"), best.get("component")),
        "fault_domain": _first_present(asset.get("fault_domain"), best.get("fault_domain")),
        "alarm_code": _first_present(slots.get("alarm_code"), best.get("alarm_code")),
        "candidate_causes": causes,
        "repair_steps": steps,
        "tools": tools,
        "spare_parts": spare_parts,
        "risk_level": risk_level,
        "safety_warnings": _safety_warnings(safety, evidence),
        "citations": citations,
        "missing_slots": list(slots.get("missing_slots", [])),
        "next_action": _next_action(list(slots.get("blocking_missing_slots", [])), safety),
    }


def _first_present(*values: object) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def _summary(query: str, best: dict, asset: dict, evidence: list[dict]) -> str:
    if not evidence:
        return f"针对“{query}”，当前知识库证据不足，需补充设备、报警码或现场现象后再诊断。"
    component = asset.get("component") or best.get("component") or "相关设备"
    fault_domain = asset.get("fault_domain") or best.get("fault_domain") or "当前故障"
    return f"针对“{query}”，系统初步定位为{component}的{fault_domain}场景，建议结合引用依据逐项排查。"


def _rank_causes(query: str, evidence: list[dict]) -> list[dict]:
    scores: dict[str, dict] = {}
    for doc_index, item in enumerate(evidence):
        base = max(0.2, 1.0 - doc_index * 0.15)
        for cause_index, raw_cause in enumerate(item.get("causes", [])):
            cause = str(raw_cause).strip()
            if not cause:
                continue
            score = base - cause_index * 0.05
            if cause in query:
                score += 0.25
            current = scores.get(cause)
            if not current or score > current["confidence"]:
                scores[cause] = {
                    "cause": cause,
                    "confidence": round(max(0.0, min(1.0, score)), 2),
                    "evidence": item.get("title", ""),
                    "check_method": _cause_check_method(cause, item),
                }
    return sorted(scores.values(), key=lambda item: item["confidence"], reverse=True)[:5]


def _cause_check_method(cause: str, item: dict) -> str:
    for step in item.get("steps", []):
        if any(token in step for token in cause[:4]):
            return step
    steps = item.get("steps", [])
    return steps[0] if steps else "结合现场参数和报警码进一步确认。"


def _build_repair_steps(evidence: list[dict]) -> list[dict]:
    steps: list[dict] = []
    seen = set()
    for item in evidence:
        for raw_step in item.get("steps", []):
            step = str(raw_step).strip()
            if not step or step in seen:
                continue
            seen.add(step)
            steps.append(
                {
                    "step": len(steps) + 1,
                    "action": step,
                    "source": item.get("title", ""),
                    "expected_result": "完成该项检查并记录结果。",
                    "risk": item.get("safety_level", "low") or "low",
                }
            )
            if len(steps) >= MAX_STEPS:
                return steps
    return steps


def _unique_from_evidence(evidence: list[dict], field: str) -> list[str]:
    values: list[str] = []
    seen = set()
    for item in evidence:
        for raw_value in item.get(field, []):
            value = str(raw_value).strip()
            if value and value not in seen:
                seen.add(value)
                values.append(value)
    return values[:MAX_ITEMS]


def _build_citations(evidence: list[dict]) -> list[dict]:
    citations: list[dict] = []
    seen = set()
    for item in evidence:
        key = (item.get("title", ""), item.get("source", ""), item.get("page", 0))
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "page": int(item.get("page") or 0),
                "score": float(item.get("score") or 0.0),
            }
        )
        if len(citations) >= MAX_CITATIONS:
            break
    return citations


def _safety_warnings(safety: dict | None, evidence: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen = set()
    for warning in [((safety or {}).get("notice") or "")]:
        if warning and warning not in seen:
            seen.add(warning)
            warnings.append(warning)
    if any(item.get("safety_level") == "high" for item in evidence):
        warning = "证据涉及高风险设备或操作，必须确认人员资质、停机、断电、挂牌和现场规程。"
        if warning not in seen:
            warnings.append(warning)
    if not warnings:
        warnings.append("可先进行远程排查，现场操作需遵守风场安全规程。")
    return warnings


def _next_action(blocking_missing_slots: list[str], safety: dict | None) -> str:
    if blocking_missing_slots:
        return "先补充缺失的设备、现象或操作场景信息，再进入诊断。"
    if safety and safety.get("risk_level") == "high":
        return "先确认人员资质、停机、断电、挂牌和现场规程要求，安全条件满足后再执行排查。"
    return "按推荐排查步骤执行，并记录处理结果用于生成工单。"
