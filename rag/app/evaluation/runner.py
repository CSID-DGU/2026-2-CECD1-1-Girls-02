from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from rag.app.evaluation.metrics import Metrics, compute_metrics
from rag.app.evaluation.schema import GroundTruthCase
from rag.app.retrieval.contracts import Retriever, SearchFilter, SearchRequest


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    case_id: str
    retrieved_document_ids: tuple[str, ...]
    latency_ms: float
    expected_insufficient: bool
    predicted_insufficient: bool


def load_jsonl(path: Path) -> list[GroundTruthCase]:
    return [GroundTruthCase.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(retriever: Retriever, cases: Iterable[GroundTruthCase], evidence_threshold: float = 0.35) -> tuple[Metrics, list[EvaluationRow]]:
    rows: list[EvaluationRow] = []
    metric_rows = []
    for case in cases:
        response = retriever.search(SearchRequest(case.query, SearchFilter(scope=case.scope), top_k=5, caller="evaluator"))
        ids = tuple(hit.document_id for hit in response.hits)
        predicted = not response.hits or response.hits[0].score < evidence_threshold
        expected = not case.relevant_document_ids
        rows.append(EvaluationRow(case.case_id, ids, response.elapsed_ms, expected, predicted))
        metric_rows.append((ids, set(case.relevant_document_ids), response.elapsed_ms, predicted))
    return compute_metrics(metric_rows), rows


def write_report(path: Path, metrics: Metrics, rows: list[EvaluationRow]) -> None:
    """Writes IDs and aggregate values only—never query text or retrieved passages."""
    payload = {"metrics": asdict(metrics), "errors": [asdict(row) for row in rows if row.expected_insufficient != row.predicted_insufficient]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
