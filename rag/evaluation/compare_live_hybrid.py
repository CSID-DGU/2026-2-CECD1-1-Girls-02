"""Compare three official search strategies with the previous private question file."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import platform
from statistics import fmean, median, quantiles
from time import perf_counter

from rag.app.evaluation.schema import GroundTruthCase
from rag.app.retrieval.bm25 import basic_tokenize, kiwi_tokenize
from rag.app.retrieval.bm25_chroma import BM25IndexManager, OfficialChromaChunkLoader
from rag.app.retrieval.contracts import KnowledgeScope, SearchRequest
from rag.app.retrieval.dense import BgeM3Embedder, ChromaDenseRetriever
from rag.app.retrieval.hybrid import HybridRetriever
from rag.app.retrieval.official import OfficialKnowledgeSearchService
from rag.evaluation.compare_live_bm25 import (
    FILTER, ROOT, FrozenLoader, ReadOnlyCollection, read_settings, records, summarize,
)

STRATEGIES = ("dense", "dense_basic", "dense_kiwi")


class ObservedSearch:
    """Record the underlying result for ranking and concordance checks."""

    def __init__(self, retriever):
        self.retriever = retriever
        self.last = None

    def search(self, request):
        self.last = self.retriever.search(request)
        return self.last


def ranked_documents(response):
    return list(dict.fromkeys(hit.document_id for hit in response.hits))


def group_results(cases, rows):
    result = {}
    for name in STRATEGIES:
        measurements = [row["results"][name] for row in rows]
        timings = [ms for item in measurements for ms in item["latencies_ms"]]
        metric_rows = [{**item, "latency_ms": fmean(item["latencies_ms"])} for item in measurements]
        result[name] = {
            **summarize(cases, metric_rows),
            "mean_latency_ms": fmean(timings),
            "p50_latency_ms": median(timings),
            "p95_latency_ms": quantiles(timings, n=20, method="inclusive")[18],
            "timed_requests": len(timings),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("--output must be outside the checkout")
    output.mkdir(mode=0o700)
    cases = [GroundTruthCase.from_dict(row) for row in records(args.questions)]
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Previous question file must contain unique cases")
    if any(case.scope is not KnowledgeScope.OFFICIAL or not case.relevant_document_ids for case in cases):
        raise ValueError("Expected positive official cases from the previous experiment")
    groups = Counter(case.metadata["variant"] for case in cases)
    if groups != {"original": 25, "ending": 11, "wording": 8, "keywords": 25}:
        raise ValueError("Unexpected question mix in previous experiment")

    settings = read_settings(args.env)
    collection = ReadOnlyCollection(settings)
    loader = OfficialChromaChunkLoader(collection, collection_name=settings.collection)
    snapshot = loader.load()
    source = {chunk.id: chunk for chunk in snapshot.chunks}
    doc_ids = {chunk.metadata["document_id"] for chunk in source.values()}
    required = ("document_id", "source_id", "document_version", "title", "category")
    if any(not isinstance(chunk.metadata.get(key), str) or not chunk.metadata[key].strip()
           for chunk in source.values() for key in required):
        raise ValueError("Required official metadata is absent")
    if any(not case.relevant_document_ids <= doc_ids for case in cases):
        raise ValueError("Some previous candidate document IDs are absent from this snapshot")

    sparse = {}
    builds = {}
    for name, tokenizer in (("basic", basic_tokenize), ("kiwi", kiwi_tokenize)):
        manager = BM25IndexManager(FrozenLoader(snapshot), tokenizer=tokenizer)
        started = perf_counter()
        status = manager.rebuild()
        builds[name] = {"ms": (perf_counter() - started) * 1000, "state": status.state,
                        "ids_verified": status.ids_verified, "snapshot_id": status.snapshot_id,
                        "indexed_chunks": status.index_chunk_count}
        if (status.state, status.ids_verified, status.snapshot_id, status.index_chunk_count) != (
            "ready", True, snapshot.snapshot_id, len(source)
        ):
            raise RuntimeError(f"{name} index failed snapshot verification")
        sparse[name] = ObservedSearch(manager)

    embedder = BgeM3Embedder(settings.embedding_model)
    started = perf_counter()
    embedder.encode([cases[0].query])
    first_embedding_ms = (perf_counter() - started) * 1000
    dense = ObservedSearch(OfficialKnowledgeSearchService(ChromaDenseRetriever(collection, embedder)))
    strategies = {
        "dense": dense,
        **{f"dense_{name}": HybridRetriever(dense, observed, rrf_k=60,
                                           dense_candidate_k=10, bm25_candidate_k=10)
           for name, observed in sparse.items()},
    }

    def search(case, name):
        response = strategies[name].search(SearchRequest(case.query, FILTER, top_k=10, caller="evaluator"))
        dense_ids = []
        for hit in dense.last.hits:
            expected = source.get(hit.chunk_id)
            if (expected is None or hit.text != expected.text or dict(hit.metadata) != expected.metadata
                    or hit.document_id != expected.metadata["document_id"]):
                raise RuntimeError(f"Dense result differs from the loaded snapshot in {case.case_id}")
            dense_ids.append(hit.chunk_id)
        return response, dense_ids

    for name in STRATEGIES:
        search(cases[0], name)
    print(f"Warmup complete · {len(source)} approved chunks · {len(cases)} cases", flush=True)
    rows = [{"case_id": case.case_id, "query": case.query,
             "variant": case.metadata["variant"], "split": case.metadata["split"],
             "relevant_document_ids": sorted(case.relevant_document_ids),
             "results": {name: {"latencies_ms": []} for name in STRATEGIES}} for case in cases]
    changes = Counter()
    for repeat in range(3):
        for index, (case, row) in enumerate(zip(cases, rows, strict=True)):
            offset = (index + repeat) % len(STRATEGIES)
            order = STRATEGIES[offset:] + STRATEGIES[:offset]
            dense_reference = None
            for name in order:
                response, dense_ids = search(case, name)
                if dense_reference is not None and dense_reference != dense_ids:
                    raise RuntimeError(f"Dense sub-ranking differs between strategies in {case.case_id}")
                dense_reference = dense_ids
                ranked = ranked_documents(response)
                item = row["results"][name]
                item["latencies_ms"].append(response.elapsed_ms)
                if repeat == 0:
                    item["ranked_document_ids"] = ranked
                    item["first_relevant_rank"] = next(
                        (rank for rank, doc in enumerate(ranked, 1) if doc in case.relevant_document_ids), None
                    )
                    if name != "dense":
                        engine = name.removeprefix("dense_")
                        item["sparse_chunk_candidates"] = [
                            {"chunk_id": hit.chunk_id, "document_id": hit.document_id}
                            for hit in sparse[engine].last.hits
                        ]
                    item["dense_chunk_candidates"] = dense_ids
                    item["top_5_document_ids"] = ranked[:5]
                elif ranked != item["ranked_document_ids"]:
                    changes[name] += 1
        print(f"Pass {repeat + 1}/3 complete", flush=True)

    final = loader.load()
    if (final.snapshot_id != snapshot.snapshot_id or final.collection_count != snapshot.collection_count
            or {chunk.id: chunk for chunk in final.chunks} != source):
        raise RuntimeError("Official collection changed during measurement")

    by_group = defaultdict(lambda: ([], []))
    for case, row in zip(cases, rows, strict=True):
        keys = [row["split"]]
        if row["split"] == "synthetic":
            keys.append(row["variant"])
        for key in keys:
            group_cases, group_rows = by_group[key]
            group_cases.append(case)
            group_rows.append(row)
    summary = {
        "environment": {"platform": platform.platform(), "python": platform.python_version()},
        "collection": snapshot.collection, "snapshot_id": snapshot.snapshot_id,
        "total_chunks": snapshot.collection_count, "official_chunks": len(source), "documents": len(doc_ids),
        "indices": builds, "model_load_plus_first_embedding_ms": first_embedding_ms,
        "repeats": 3, "ranking_changes_after_first_pass": dict(changes), "groups": {
            key: {"questions": len(group_cases), **group_results(group_cases, group_rows)}
            for key, (group_cases, group_rows) in by_group.items()
        },
    }
    (output / "question-results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Snapshot and report verified", flush=True)


if __name__ == "__main__":
    main()
