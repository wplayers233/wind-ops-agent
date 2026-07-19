DEMO_METRICS_NOTE = "静态展示值，仅用于本地 Demo 门禁，不代表线上实时监控或真实生产评估。"


def get_system_metrics() -> dict:
    return {
        "documents": 1247,
        "machine_types": 3,
        "recall_at_5": 0.87,
        "qa_accuracy": 0.89,
        "mean_resolution_minutes": 11,
        "self_service_rate": 0.68,
        "context_precision": 0.92,
        "context_recall": 0.88,
        "faithfulness": 0.91,
        "response_relevancy": 0.89,
        "metrics_kind": "static_demo_metrics",
        "metrics_note": DEMO_METRICS_NOTE,
        "retriever_status": "online",
        "pipeline_status": "RAG Pipeline Online",
        "service_status": "ok",
        "api_version": "0.5.0",
        "session_id": "2026-0710-03",
    }
