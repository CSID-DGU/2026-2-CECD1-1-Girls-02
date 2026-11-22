from __future__ import annotations

from dataclasses import dataclass
from math import log2
from statistics import quantiles
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class Metrics:
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    p95_latency_ms: float
    insufficient_evidence_detection_rate: float | None = None
    insufficient_evidence_false_positive_rate: float | None = None


def _dcg(ids: Sequence[str], relevant: set[str], k: int = 5) -> float:
    return sum(1 / log2(rank + 1) for rank, doc_id in enumerate(ids[:k], 1) if doc_id in relevant)


def compute_metrics(rows: Iterable[tuple[Sequence[str], set[str], float, bool | None]]) -> Metrics:
    rows = list(rows)
    if not rows:
        raise ValueError("at least one evaluation result is required")
    recalls, reciprocal_ranks, ndcgs, latencies = [], [], [], []
    expected_insufficient: list[bool] = []
    predicted_insufficient: list[bool] = []
    for ids, relevant, latency, insufficient in rows:
        top = ids[:5]
        recalls.append(float(bool(set(top) & relevant)))
        reciprocal_ranks.append(next((1 / rank for rank, doc_id in enumerate(top, 1) if doc_id in relevant), 0.0))
        ideal = _dcg(list(relevant), relevant)
        ndcgs.append(_dcg(top, relevant) / ideal if ideal else 0.0)
        latencies.append(latency)
        if insufficient is not None:
            expected_insufficient.append(not relevant)
            predicted_insufficient.append(insufficient)
    p95 = max(latencies) if len(latencies) == 1 else quantiles(latencies, n=20, method="inclusive")[18]
    if not expected_insufficient:
        detection = false_positive = None
    else:
        positives = sum(expected_insufficient)
        negatives = len(expected_insufficient) - positives
        detection = sum(e and p for e, p in zip(expected_insufficient, predicted_insufficient)) / positives if positives else None
        false_positive = sum(not e and p for e, p in zip(expected_insufficient, predicted_insufficient)) / negatives if negatives else None
    return Metrics(sum(recalls) / len(rows), sum(reciprocal_ranks) / len(rows), sum(ndcgs) / len(rows), p95, detection, false_positive)
