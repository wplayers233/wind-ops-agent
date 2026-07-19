from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any


@dataclass
class TaskIntent:
    name: str
    confidence: float
    matched_terms: list[str]


@dataclass
class AssetIntent:
    model: str | None
    system: str | None
    component: str | None
    fault_domain: str | None
    manufacturer: str | None
    confidence: float
    matched_terms: list[str]


@dataclass
class IntentSlots:
    alarm_code: str | None
    symptom: str | None
    model: str | None
    turbine_id: str | None
    location: str | None
    has_image: bool
    image_type: str | None
    operation_status: str | None
    urgency: str | None
    missing_slots: list[str]
    blocking_missing_slots: list[str]
    optional_missing_slots: list[str]


@dataclass
class RouteDecision:
    workflow: str
    need_clarification: bool
    clarification_questions: list[str]
    retrieval_filters: dict
    next_nodes: list[str]


@dataclass
class IntentAnalysis:
    task: TaskIntent
    asset: AssetIntent
    slots: IntentSlots
    route: RouteDecision
    confidence: float
    reason: str

    @property
    def intent(self) -> str:
        return self.task.name


class IntentRouter:
    KNOWLEDGE_FILTER_FIELDS = {"model", "system", "component", "fault_domain", "alarm_code", "doc_type"}
    FOLLOWUP_TERMS = ("这个", "这", "该", "继续", "上面", "刚才", "它", "怎么处理", "怎么办")
    HIGH_RISK_TERMS = ("高压", "带电", "断电", "挂牌", "高空", "登塔", "爬塔", "吊装", "开柜", "电气柜")

    def __init__(self) -> None:
        self.rules = self._load_rules()

    def route(self, query: str, memory_state: dict | None) -> IntentAnalysis:
        return self.analyze(query, memory_state or {})

    def analyze(self, query: str, memory_state: dict | None) -> IntentAnalysis:
        memory_state = memory_state or {}
        normalized = self._normalize(query)
        task = self._detect_task(normalized)
        asset = self._detect_asset(query, normalized)
        slots = self._extract_slots(query, normalized, asset)
        asset, slots = self._merge_memory(normalized, task, asset, slots, memory_state)
        slots = self._check_missing_slots(normalized, task, asset, slots, memory_state)
        route = self._build_route(task, asset, slots)
        return self._build_analysis(task, asset, slots, route)

    def _load_rules(self) -> dict[str, Any]:
        fallback = {
            "task_rules": [
                {"name": "health_check", "priority": 120, "patterns": ["在吗", "你好", "health", "系统在吗"], "terms": []},
                {"name": "safety_check", "priority": 115, "patterns": ["安全", "风险", "高压", "带电", "高空"], "terms": []},
                {"name": "ticket_create", "priority": 110, "patterns": ["工单", "报修", "派单"], "terms": []},
                {"name": "fault_diagnosis", "priority": 105, "patterns": ["故障", "报警", "异常", "排查", "原因"], "terms": []},
                {"name": "repair_guidance", "priority": 90, "patterns": ["怎么处理", "维修", "更换", "步骤"], "terms": []},
                {"name": "diagram_lookup", "priority": 88, "patterns": ["图纸", "接线图", "原理图"], "terms": []},
                {"name": "document_retrieval", "priority": 80, "patterns": ["文档", "资料", "手册"], "terms": []},
            ],
            "asset_rules": {
                "systems": [
                    {"name": "pitch_system", "component": "变桨系统", "terms": ["变桨", "pitch"]},
                    {"name": "yaw_system", "component": "偏航系统", "terms": ["偏航", "yaw"]},
                    {"name": "converter_system", "component": "变流器", "terms": ["变流器", "converter"]},
                    {"name": "electrical_system", "component": "电气柜", "terms": ["高压", "电气柜", "控制柜"]},
                ],
                "fault_domains": [{"name": "electrical_risk", "terms": ["高压", "带电", "断电", "挂牌"]}],
                "locations": ["塔筒", "机舱", "轮毂", "塔基"],
                "operation_statuses": ["运行中", "已停机", "停机", "待机"],
            },
            "slot_rules": {
                "model_patterns": [r"[A-Za-z]{0,4}\d{2,4}-?\d+(?:\.\d+)?MW", r"\d+(?:\.\d+)?MW"],
                "alarm_code_patterns": [r"[A-Z]{2,}[_-][A-Z0-9_]+", r"E-\d+", r"[A-Z]+\d{2,}"],
                "turbine_id_patterns": [r"#\d+", r"[A-Za-z]{1,4}-?\d{1,4}号?机组"],
                "image_terms": ["图片", "照片", "截图", "图纸", "接线图"],
                "urgency_high_terms": ["紧急", "停机", "跳闸", "高压", "冒烟", "无法复位", "高空", "带电"],
                "urgency_medium_terms": ["报警", "异常", "过温", "过压", "过载"],
            },
        }
        rules_path = Path(__file__).resolve().parents[1] / "data" / "intent_rules.json"
        try:
            loaded = json.loads(rules_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return fallback
        if not isinstance(loaded, dict) or not loaded.get("task_rules"):
            return fallback
        loaded.setdefault("asset_rules", fallback["asset_rules"])
        loaded.setdefault("slot_rules", fallback["slot_rules"])
        return loaded

    def _normalize(self, query: str) -> str:
        return (query or "").strip().lower()

    def _detect_task(self, normalized: str) -> TaskIntent:
        if not normalized:
            return TaskIntent(name="llm_fallback", confidence=0.45, matched_terms=[])
        scored: list[tuple[int, int, str, list[str]]] = []
        for rule in self.rules.get("task_rules", []):
            matched_terms = self._match_patterns_and_terms(rule, normalized)
            if matched_terms:
                scored.append((int(rule.get("priority", 0)), len(matched_terms), rule.get("name", "llm_fallback"), matched_terms))
        if scored:
            safety = [item for item in scored if item[2] == "safety_check"]
            if safety:
                scored = safety
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            priority, matched_count, name, matched_terms = scored[0]
            confidence = min(0.98, 0.7 + priority / 600 + matched_count * 0.035)
            return TaskIntent(name=name, confidence=confidence, matched_terms=matched_terms)
        return TaskIntent(name="llm_fallback", confidence=0.4, matched_terms=[])

    def _match_patterns_and_terms(self, rule: dict, normalized: str) -> list[str]:
        matched: list[str] = []
        for pattern in rule.get("patterns", []):
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                matched.append(pattern)
        for term in rule.get("terms", []):
            if term.lower() in normalized:
                matched.append(term)
        return self._unique(matched)

    def _detect_asset(self, query: str, normalized: str) -> AssetIntent:
        matched_terms: list[str] = []
        system = component = fault_domain = manufacturer = None
        for item in self.rules.get("asset_rules", {}).get("systems", []):
            terms = [term for term in item.get("terms", []) if term.lower() in normalized]
            if terms:
                system = item.get("name")
                component = item.get("component")
                matched_terms.extend(terms)
                break
        for item in self.rules.get("asset_rules", {}).get("fault_domains", []):
            terms = [term for term in item.get("terms", []) if term.lower() in normalized]
            if terms:
                fault_domain = item.get("name")
                matched_terms.extend(terms)
                break
        model = self._first_regex_match(query, self.rules.get("slot_rules", {}).get("model_patterns", []))
        if model:
            matched_terms.append(model)
        confidence = min(0.95, (0.42 if system or component else 0) + (0.32 if fault_domain else 0) + (0.16 if model else 0) + min(0.1, len(matched_terms) * 0.02))
        return AssetIntent(model, system, component, fault_domain, manufacturer, confidence, self._unique(matched_terms))

    def _extract_slots(self, query: str, normalized: str, asset: AssetIntent) -> IntentSlots:
        slot_rules = self.rules.get("slot_rules", {})
        alarm_code = self._first_regex_match(query, slot_rules.get("alarm_code_patterns", []))
        model = asset.model or self._first_regex_match(query, slot_rules.get("model_patterns", []))
        turbine_id = self._first_regex_match(query, slot_rules.get("turbine_id_patterns", []))
        location = self._first_term_match(normalized, self.rules.get("asset_rules", {}).get("locations", []))
        operation_status = self._first_term_match(normalized, self.rules.get("asset_rules", {}).get("operation_statuses", []))
        image_type = self._first_term_match(normalized, slot_rules.get("image_terms", []))
        symptom = self._extract_symptom(normalized, asset)
        return IntentSlots(alarm_code, symptom, model, turbine_id, location, image_type is not None, image_type, operation_status, self._detect_urgency(normalized), [], [], [])

    def _first_regex_match(self, query: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, query, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _first_term_match(self, normalized: str, terms: list[str]) -> str | None:
        for term in terms:
            if term.lower() in normalized:
                return term
        return None

    def _extract_symptom(self, normalized: str, asset: AssetIntent) -> str | None:
        symptom_terms: list[str] = []
        for item in self.rules.get("asset_rules", {}).get("fault_domains", []):
            symptom_terms.extend(item.get("terms", []))
        symptom_terms.extend(["故障", "报警", "异常", "报错", "跳闸", "无法复位", "排查", "风险"])
        for term in symptom_terms:
            if term.lower() in normalized:
                return term
        return asset.fault_domain

    def _detect_urgency(self, normalized: str) -> str:
        slot_rules = self.rules.get("slot_rules", {})
        if any(term.lower() in normalized for term in slot_rules.get("urgency_high_terms", [])):
            return "high"
        if any(term.lower() in normalized for term in slot_rules.get("urgency_medium_terms", [])):
            return "medium"
        return "low"

    def _merge_memory(self, normalized: str, task: TaskIntent, asset: AssetIntent, slots: IntentSlots, memory_state: dict) -> tuple[AssetIntent, IntentSlots]:
        if task.name in {"safety_check", "ticket_create", "health_check"}:
            return asset, slots
        if asset.component or asset.system or not self._is_followup(normalized):
            return asset, slots
        history = memory_state.get("history", []) or []
        last = history[-1] if history else {}
        last_component = last.get("component", "")
        if not last_component:
            return asset, slots
        for item in self.rules.get("asset_rules", {}).get("systems", []):
            if item.get("component") == last_component:
                asset.system = item.get("name")
                asset.component = last_component
                asset.matched_terms = self._unique([*asset.matched_terms, last_component])
                asset.confidence = max(asset.confidence, 0.62)
                break
        if not slots.symptom and last.get("content"):
            slots.symptom = last.get("content")
        return asset, slots

    def _is_followup(self, normalized: str) -> bool:
        return bool(normalized and any(term in normalized for term in self.FOLLOWUP_TERMS))

    def _check_missing_slots(self, normalized: str, task: TaskIntent, asset: AssetIntent, slots: IntentSlots, memory_state: dict) -> IntentSlots:
        blocking: list[str] = []
        optional: list[str] = []
        history = memory_state.get("history", []) or []
        has_context = bool(history)
        high_risk = task.name == "safety_check" and any(term in normalized for term in self.HIGH_RISK_TERMS)
        if task.name == "fault_diagnosis":
            if not (asset.system or asset.component or slots.symptom):
                blocking.extend(["component", "specific_symptom"])
            if not slots.model:
                optional.append("model")
            if not slots.alarm_code:
                optional.append("alarm_code")
        elif task.name == "ticket_create":
            if not slots.symptom and not has_context:
                blocking.append("symptom")
        elif task.name == "safety_check":
            if high_risk and not (asset.system or asset.component):
                blocking.append("component")
            if high_risk and not slots.operation_status:
                blocking.append("operation_status")
            if not high_risk and not (asset.system or asset.component or slots.operation_status or has_context):
                blocking.append("operation_context")
            elif not slots.operation_status:
                optional.append("operation_status")
        elif task.name == "diagram_lookup":
            if not (asset.system or asset.component):
                optional.append("component")
        elif task.name == "llm_fallback" and normalized:
            optional.extend(["component", "symptom"])
        slots.blocking_missing_slots = self._unique(blocking)
        slots.optional_missing_slots = self._unique(optional)
        slots.missing_slots = self._unique([*blocking, *optional])
        return slots

    def _build_route(self, task: TaskIntent, asset: AssetIntent, slots: IntentSlots) -> RouteDecision:
        workflow_map = {
            "health_check": "health_workflow",
            "ticket_create": "ticket_workflow",
            "safety_check": "safety_workflow",
            "diagram_lookup": "diagram_workflow",
            "document_retrieval": "retrieval_workflow",
            "fault_diagnosis": "diagnosis_workflow",
            "repair_guidance": "repair_workflow",
            "llm_fallback": "fallback_workflow",
        }
        workflow = workflow_map.get(task.name, "fallback_workflow")
        node_map = {
            "diagnosis_workflow": ["retrieval", "diagnosis", "repair_plan", "safety_check", "answer_compose"],
            "repair_workflow": ["retrieval", "repair_plan", "safety_check", "answer_compose"],
            "retrieval_workflow": ["retrieval", "answer_compose"],
            "safety_workflow": ["safety_check", "answer_compose"],
            "ticket_workflow": ["retrieval", "ticket_summary"],
            "diagram_workflow": ["diagram_retrieval", "answer_compose"],
            "health_workflow": ["answer_compose"],
            "fallback_workflow": ["retrieval", "answer_compose"],
        }
        questions = self._build_clarification_questions(slots)
        return RouteDecision(workflow, bool(slots.blocking_missing_slots), questions, self._build_retrieval_filters(task, asset, slots), node_map[workflow])

    def _build_retrieval_filters(self, task: TaskIntent, asset: AssetIntent, slots: IntentSlots) -> dict:
        filters: dict[str, Any] = {
            "model": slots.model or asset.model,
            "system": asset.system,
            "component": asset.component,
            "fault_domain": asset.fault_domain,
            "alarm_code": slots.alarm_code,
        }
        doc_type_map = {
            "fault_diagnosis": ["manual", "procedure", "case", "ocr", "diagram"],
            "repair_guidance": ["procedure", "manual", "case"],
            "diagram_lookup": ["diagram", "ocr"],
            "document_retrieval": ["manual", "procedure", "case", "slide", "ocr", "diagram"],
            "safety_check": ["procedure", "manual", "checklist"],
            "ticket_create": ["case", "manual", "procedure"],
        }
        if task.name in doc_type_map:
            filters["doc_type"] = doc_type_map[task.name]
        return {key: value for key, value in filters.items() if key in self.KNOWLEDGE_FILTER_FIELDS and value not in (None, "", [])}

    def _build_clarification_questions(self, slots: IntentSlots) -> list[str]:
        question_map = {
            "component": "请补充具体设备部件或系统，例如变桨系统、齿轮箱、变流器。",
            "specific_symptom": "请补充具体现象或报警信息，例如通讯中断、油温过高、母线过压。",
            "symptom": "请补充故障现象、初判原因或处理过程。",
            "operation_context": "请说明具体操作场景，例如是否需要停机、断电、登塔或打开电气柜。",
            "operation_status": "请说明当前设备或作业状态，例如运行中、已停机、已断电挂牌。",
        }
        return [question_map[item] for item in slots.blocking_missing_slots if item in question_map]

    def _build_analysis(self, task: TaskIntent, asset: AssetIntent, slots: IntentSlots, route: RouteDecision) -> IntentAnalysis:
        confidence_parts = [task.confidence]
        if asset.confidence:
            confidence_parts.append(asset.confidence)
        confidence = sum(confidence_parts) / len(confidence_parts)
        if slots.blocking_missing_slots:
            confidence = max(0.35, confidence - 0.2)
        reason_parts = [f"任务命中：{'、'.join(task.matched_terms[:3])}" if task.matched_terms else "任务未明确，进入检索兜底"]
        if asset.matched_terms:
            reason_parts.append(f"对象命中：{'、'.join(asset.matched_terms[:4])}")
        if slots.missing_slots:
            reason_parts.append(f"缺失槽位：{'、'.join(slots.missing_slots)}")
        reason_parts.append(f"路由：{route.workflow}")
        return IntentAnalysis(task, asset, slots, route, round(min(0.98, confidence), 2), "；".join(reason_parts))

    def _unique(self, values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
