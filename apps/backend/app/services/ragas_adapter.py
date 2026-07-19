from __future__ import annotations


def run_ragas(dataset: list[dict], answers: list[dict]) -> dict:
    """Execute Ragas when installed; callers are responsible for fallback."""
    try:
        from ragas import evaluate
        try:
            from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
        except ImportError:
            from ragas import EvaluationDataset, SingleTurnSample
        from ragas.metrics import ContextPrecision, ContextRecall, Faithfulness
        try:
            from ragas.metrics import ResponseRelevancy
            relevancy = ResponseRelevancy()
        except ImportError:
            from ragas.metrics import AnswerRelevancy
            relevancy = AnswerRelevancy()
    except ImportError as exc:
        raise RuntimeError("RAGAS is not installed; install the optional ragas dependency") from exc
    samples = [SingleTurnSample(user_input=case["question"], response=answer.get("answer", ""), retrieved_contexts=answer.get("contexts", []), reference=case.get("reference_answer", ""), reference_contexts=case.get("reference_contexts", [])) for case, answer in zip(dataset, answers)]
    result = evaluate(EvaluationDataset(samples=samples), metrics=[ContextPrecision(), ContextRecall(), Faithfulness(), relevancy])
    frame = result.to_pandas()
    return {"metrics_kind": "ragas", "dataset_size": len(samples), "scores": frame.mean(numeric_only=True).to_dict()}