import json
from pathlib import Path

from scripts import evaluate_v2


def test_document_recall_and_no_evidence_metrics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = [
        {
            "query": "multi-document question",
            "relevant_document_titles": ["Document A", "Document B"],
        },
        {
            "query": "unsupported question",
            "expected_no_evidence": True,
        },
    ]
    dataset_path = tmp_path / "retrieval_dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    def fake_search(query: str, top_k: int, corpus_type: str):
        assert top_k == 3
        assert corpus_type == "enterprise"
        if query == "unsupported question":
            return []
        return [
            {"title": "Document A", "relevance": 0.9},
            {"title": "Unrelated", "relevance": 0.5},
            {"title": "Document A", "relevance": 0.4},
        ]

    monkeypatch.setattr(evaluate_v2, "search", fake_search)
    metrics, errors = evaluate_v2.evaluate_retrieval(
        dataset_path,
        corpus_type="enterprise",
        top_k=3,
    )

    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["document_recall_at_k"] == 0.5
    assert metrics["mrr"] == 1.0
    assert metrics["chunk_precision_at_k"] == 2 / 3
    assert metrics["no_evidence_accuracy"] == 1.0
    assert errors[0]["kind"] == "retrieval_miss"
    assert errors[0]["found_document_titles"] == ["Document A"]
