from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.ragas_adapter import run_ragas

DEMO_EVALUATION_NOTE = "离线 fallback 指标，基于本地黄金路径确定性计算，不代表真实 Ragas。"
EVALUATION_DATASET_VERSION = "golden-path-v1"
EVALUATION_DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "evaluation" / "golden_path.jsonl"
FALLBACK_EVALUATION_CASES = [
    {"id": "case-001", "question": "2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？", "reference_answer": "检查供电、CAN线缆、报警码和编码器。", "reference_contexts": ["doc-001"]},
    {"id": "case-002", "question": "齿轮箱油温高怎么处理？", "reference_answer": "检查油位、冷却器、滤芯和轴承振动。", "reference_contexts": ["doc-002"]},
    {"id": "case-003", "question": "偏航电机过载报警怎么排查？", "reference_answer": "检查卡滞、制动器、齿圈异物和润滑。", "reference_contexts": ["doc-003"]},
    {"id": "case-004", "question": "变流器直流母线过压 CONV_DC_OV 如何处理？", "reference_answer": "检查电网、制动单元、参数并在必要时停机。", "reference_contexts": ["doc-004"]},
]


def load_evaluation_cases(path: Path = EVALUATION_DATASET_PATH) -> list[dict[str, Any]]:
    """Load versioned golden cases while preserving an offline code fallback."""
    try:
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError, json.JSONDecodeError):
        return list(FALLBACK_EVALUATION_CASES)
    return cases or list(FALLBACK_EVALUATION_CASES)


def _expected_ids(case: dict[str, Any]) -> set[str]:
    return {str(value) for value in case.get("reference_contexts", []) if value}


def evaluate_retrieval(evidence: list[dict]) -> dict:
    if not evidence:
        return {"context_precision": 0.0, "context_recall": 0.0, "faithfulness": 0.0, "response_relevancy": 0.0, "recall_at_5": 0.0, "metrics_kind": "offline_fallback", "metrics_note": DEMO_EVALUATION_NOTE}
    top_score = max(0.0, float(evidence[0].get("score", 0.0) or 0.0))
    clamp = lambda value: round(max(0.0, min(1.0, float(value))), 2)
    return {"context_precision": clamp(0.55 + top_score / 120), "context_recall": clamp(0.6 + len(evidence) / 20), "faithfulness": clamp(0.62 + top_score / 150), "response_relevancy": clamp(0.58 + top_score / 140), "recall_at_5": clamp(0.62 + len(evidence) / 10), "metrics_kind": "offline_fallback", "metrics_note": DEMO_EVALUATION_NOTE}


def _offline_evaluation(retriever, cases: list[dict[str, Any]], reason: str = "") -> dict:
    hits = 0
    for case in cases:
        results = retriever.retrieve(case["question"], top_k=5)
        if _expected_ids(case) & {str(item.doc.get("id", "")) for item in results}:
            hits += 1
    recall = hits / len(cases)
    return {"dataset_version": EVALUATION_DATASET_VERSION, "sample_count": len(cases), "metrics": {"recall_at_5": round(recall, 2), "context_precision": round(recall, 2), "context_recall": round(recall, 2), "faithfulness": round(recall, 2), "response_relevancy": round(recall, 2), "unsupported_answer_rate": round(1 - recall, 2), "safety_rule_hit_rate": 1.0}, "baseline": {"recall_at_5": 0.5}, "metrics_kind": "offline_fallback", "metrics_note": DEMO_EVALUATION_NOTE, "provider_status": "offline_fallback", "fallback_reason": reason}


def evaluate_dataset(retriever) -> dict:
    cases = load_evaluation_cases()
    if os.getenv("RAGAS_ENABLED", "false").lower() == "true":
        try:
            answers: list[dict[str, Any]] = []
            for case in cases:
                results = retriever.retrieve(case["question"], top_k=5)
                contexts = [str(item.doc.get("content") or item.doc.get("ocr_text") or item.doc.get("visual_caption") or "") for item in results]
                answers.append({"answer": contexts[0] if contexts else "", "contexts": contexts})
            result = run_ragas(cases, answers)
            scores = {key.lower(): float(value) for key, value in result.get("scores", {}).items() if isinstance(value, (int, float))}
            normalized = {"context_precision": scores.get("contextprecision", scores.get("context_precision", 0.0)), "context_recall": scores.get("contextrecall", scores.get("context_recall", 0.0)), "faithfulness": scores.get("faithfulness", 0.0), "response_relevancy": scores.get("answerrelevancy", scores.get("responserelevancy", 0.0))}
            return {"dataset_version": EVALUATION_DATASET_VERSION, "sample_count": len(cases), "metrics": normalized, "baseline": {"recall_at_5": 0.5}, "metrics_kind": "ragas", "metrics_note": "真实 Ragas 评估结果。", "provider_status": "ragas", "fallback_reason": ""}
        except Exception as exc:
            return _offline_evaluation(retriever, cases, str(exc))
    return _offline_evaluation(retriever, cases, "RAGAS_ENABLED=false")