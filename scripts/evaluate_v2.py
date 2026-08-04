"""Deterministic routing/RAG evaluation; no LLM-as-judge required."""
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from app.llm.mock_llm import route_with_rules
from app.rag.indexer import search


def evaluate_retrieval(
    dataset_path: Path,
    *,
    corpus_type: str,
    top_k: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate document-level recall and no-evidence behavior for one corpus.

    Search returns chunks, while the gold set deliberately uses stable document
    titles. Recall therefore measures whether each relevant document contributes
    at least one chunk to the first ``top_k`` results.
    """
    rows = json.loads(dataset_path.read_text(encoding="utf-8"))
    positive_count = 0
    no_evidence_count = 0
    hits = 0
    reciprocal_rank = 0.0
    recall_sum = 0.0
    relevant_chunk_results = 0
    returned_chunk_results = 0
    zero_score_results = 0
    correct_no_evidence = 0
    errors: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []

    for row in rows:
        results = search(row["query"], top_k=top_k, corpus_type=corpus_type)
        titles = [item["title"] for item in results]
        zero_score_results += sum(1 for item in results if float(item.get("relevance", 0)) <= 0)

        if row.get("expected_no_evidence"):
            no_evidence_count += 1
            passed = not results
            correct_no_evidence += int(passed)
            sample = {
                "query": row["query"],
                "kind": "no_evidence",
                "passed": passed,
                "retrieved_titles": titles,
            }
            if not passed:
                errors.append({
                    "kind": "retrieval_false_positive",
                    "corpus_type": corpus_type,
                    "query": row["query"],
                    "titles": titles,
                })
            samples.append(sample)
            continue

        relevant = set(row["relevant_document_titles"])
        positive_count += 1
        found = relevant.intersection(titles)
        recall = len(found) / len(relevant)
        first_rank = next((index for index, title in enumerate(titles, 1) if title in relevant), None)
        hit = first_rank is not None
        hits += int(hit)
        reciprocal_rank += 1 / first_rank if first_rank else 0
        recall_sum += recall
        relevant_chunk_results += sum(1 for title in titles if title in relevant)
        returned_chunk_results += len(titles)
        sample = {
            "query": row["query"],
            "kind": "positive",
            "relevant_document_titles": sorted(relevant),
            "found_document_titles": sorted(found),
            "retrieved_titles": titles,
            "recall_at_k": recall,
            "first_relevant_rank": first_rank,
        }
        if recall < 1:
            errors.append({
                **sample,
                "kind": "retrieval_miss",
                "corpus_type": corpus_type,
            })
        samples.append(sample)

    metrics = {
        "dataset": dataset_path.name,
        "corpus_type": corpus_type,
        "top_k": top_k,
        "positive_queries": positive_count,
        "no_evidence_queries": no_evidence_count,
        "hit_rate_at_k": hits / positive_count if positive_count else None,
        "document_recall_at_k": recall_sum / positive_count if positive_count else None,
        "mrr": reciprocal_rank / positive_count if positive_count else None,
        "chunk_precision_at_k": (
            relevant_chunk_results / returned_chunk_results if returned_chunk_results else None
        ),
        "no_evidence_accuracy": (
            correct_no_evidence / no_evidence_count if no_evidence_count else None
        ),
        "zero_score_results": zero_score_results,
        "samples": samples,
    }
    return metrics, errors


def evaluate() -> dict[str, object]:
    dataset_dir = ROOT_DIR / "tests" / "evaluation"
    routing = json.loads((dataset_dir / "routing_dataset.json").read_text(encoding="utf-8"))
    errors, confusion, category = [], Counter(), defaultdict(lambda: [0, 0])
    tool_correct = forbidden_calls = 0
    for row in routing:
        decision = route_with_rules(row["query"])
        ok = decision.route == row["expected_route"]
        category[row["expected_route"]][1] += 1; category[row["expected_route"]][0] += int(ok)
        confusion[(row["expected_route"], decision.route)] += 1
        tool_correct += int(set(decision.required_tools) == set(row["expected_tools"]))
        forbidden_calls += int(bool(set(decision.required_tools) & set(row["forbidden_tools"])))
        if not ok:
            errors.append({"kind": "route", "query": row["query"], "expected": row["expected_route"], "actual": decision.route})
    retrieval: dict[str, Any] = {}
    for corpus_type in ("mock", "enterprise"):
        metrics, retrieval_errors = evaluate_retrieval(
            dataset_dir / f"retrieval_{corpus_type}_dataset.json",
            corpus_type=corpus_type,
            top_k=5,
        )
        retrieval[corpus_type] = metrics
        errors.extend(retrieval_errors)
    result = {
        "generated_at": datetime.now(UTC).isoformat(), "mode": "deterministic_mock_and_configured_retrieval",
        "routing": {"total": len(routing), "accuracy": sum(v[0] for v in category.values()) / len(routing),
                    "per_category": {k: v[0] / v[1] for k, v in category.items()},
                    "confusion_matrix": {f"{a}->{b}": n for (a, b), n in confusion.items()},
                    "tool_accuracy": tool_correct / len(routing), "forbidden_tool_rate": forbidden_calls / len(routing)},
        "retrieval": retrieval,
        "errors": errors,
    }
    out = ROOT_DIR / "artifacts" / "evaluation"; out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    mock_metrics = retrieval["mock"]
    enterprise_metrics = retrieval["enterprise"]
    markdown = (
        "# V2 确定性评测\n\n"
        f"- 路由准确率：{result['routing']['accuracy']:.2%}\n"
        f"- 工具选择准确率：{result['routing']['tool_accuracy']:.2%}\n"
        f"- Mock 文档 Recall@5：{mock_metrics['document_recall_at_k']:.2%}\n"
        f"- Enterprise 文档 Recall@5：{enterprise_metrics['document_recall_at_k']:.2%}\n"
        f"- Enterprise Hit Rate@5：{enterprise_metrics['hit_rate_at_k']:.2%}\n"
        f"- Enterprise MRR：{enterprise_metrics['mrr']:.3f}\n"
        f"- Enterprise 无证据正确率：{enterprise_metrics['no_evidence_accuracy']:.2%}\n"
        f"- 错误样本：{len(errors)}\n"
    )
    (out / "report.md").write_text(markdown, encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
