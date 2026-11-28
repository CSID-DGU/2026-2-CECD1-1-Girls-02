"""Compare Basic and Kiwi against one read-only Chroma snapshot.

Run from the repository with python -m rag.evaluation.compare_live_bm25.
Question-level results contain private data and belong outside the checkout.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from statistics import fmean
from urllib.parse import quote
from urllib.request import Request, urlopen

from rag.app.evaluation.metrics import compute_metrics
from rag.app.evaluation.runner import load_jsonl
from rag.app.evaluation.schema import GroundTruthCase
from rag.app.retrieval.bm25 import basic_tokenize, kiwi_tokenize
from rag.app.retrieval.bm25_chroma import (
    BM25IndexManager,
    OfficialChromaChunkLoader,
    OfficialChunkSnapshot,
)
from rag.app.retrieval.contracts import KnowledgeScope, SearchFilter, SearchRequest
from rag.app.retrieval.dense import BgeM3Embedder, ChromaDenseRetriever
from rag.app.retrieval.hybrid import HybridRetriever
from rag.app.retrieval.official import OfficialKnowledgeSearchService, OfficialSearchSettings
from rag.scripts.analyze_bm25_tokenization import _load_faq, _paraphrase

ROOT = Path(__file__).resolve().parents[2]
CUTOFFS = (1, 3, 5, 10)
FILTER = SearchFilter(scope=KnowledgeScope.OFFICIAL)


def request_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


class ReadOnlyCollection:
    """Expose the Chroma v2 read endpoints required by the existing loader."""

    def __init__(self, settings: OfficialSearchSettings) -> None:
        api = f"http://{settings.host}:{settings.port}/api/v2"
        request_json(f"{api}/heartbeat")
        collections = f"{api}/tenants/default_tenant/databases/default_database/collections"
        collection = request_json(f"{collections}/{quote(settings.collection, safe='')}")
        self.url = f"{collections}/{collection['id']}"

    def count(self) -> int:
        return request_json(f"{self.url}/count")

    def get(self, **kwargs) -> dict:
        return request_json(f"{self.url}/get", kwargs)

    def query(self, *, query_embeddings, **kwargs) -> dict:
        vectors = [[float(value) for value in vector] for vector in query_embeddings]
        return request_json(f"{self.url}/query", {"query_embeddings": vectors, **kwargs})


@dataclass(frozen=True)
class FrozenLoader:
    snapshot: OfficialChunkSnapshot

    @property
    def collection_name(self) -> str:
        return self.snapshot.collection

    def load(self) -> OfficialChunkSnapshot:
        return self.snapshot


def read_settings(path: Path) -> OfficialSearchSettings:
    keys = {"CHROMA_HOST", "CHROMA_PORT", "CHROMA_OFFICIAL_COLLECTION", "RAG_EMBEDDING_MODEL"}
    values = {}
    for line in path.read_text().splitlines():
        key, _, value = line.strip().removeprefix("export ").partition("=")
        if key.strip() in keys:
            values[key.strip()] = value.strip().strip("\"'")
    values.update({k: os.environ[k] for k in keys if k in os.environ})
    return OfficialSearchSettings.from_env(values)


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def exploratory_cases(faq: Path, template: Path, variants: Path, snapshot) -> list[GroundTruthCase]:
    by_source = defaultdict(set)
    for chunk in snapshot.chunks:
        if chunk.metadata.get("document_type") == "FAQ":
            by_source[chunk.metadata["source_id"]].add(chunk.metadata["document_id"])

    sources = {
        f"faq:{item['id']}": item["title"].strip()
        for item in _load_faq(faq)
        if item["active"] is True and item["title"].strip()
    }
    prior = {row["source_id"]: row["query"] for row in records(variants)}
    priority = [row["relevant_source_id"] for row in records(template)]
    ordered = dict.fromkeys(priority + sorted(sources))
    selected = [source for source in ordered if source in sources and len(by_source[source]) == 1][:25]
    if len(selected) < 20:
        raise ValueError(f"Only {len(selected)} source questions mapped unambiguously to Chroma")

    cases = []
    for index, source in enumerate(selected, 1):
        original = sources[source]
        ending = _paraphrase(original)
        ending_query = prior.get(source) or (ending[0] if ending else "")
        words = list(dict.fromkeys(re.findall(r"[0-9A-Za-z가-힣]{2,}", original)))
        longest = set(sorted(words, key=len, reverse=True)[:3])
        keyword_query = " ".join(word for word in words if word in longest)
        wording = re.sub(r"어떻게|무엇|언제|어디", lambda m: {
            "어떻게": "어떤 방법으로", "무엇": "어떤 것", "언제": "어느 시점에", "어디": "어느 곳",
        }[m[0]], original, count=1)
        seen = set()
        for kind, query in (("original", original), ("ending", ending_query),
                            ("wording", wording), ("keywords", keyword_query)):
            if not query or query in seen:
                continue
            seen.add(query)
            cases.append(GroundTruthCase.from_dict({
                "case_id": f"faq-{index:02d}-{kind}",
                "query": query,
                "scope": "official",
                "relevant_document_ids": sorted(by_source[source]),
                "metadata": {
                    "split": "original" if kind == "original" else "synthetic",
                    "variant": kind,
                    "source": "company_faq" if kind == "original" else "rule_based",
                    "review_status": "needs_human_review",
                    "source_id": source,
                },
            }))
    return cases


def evaluate(retriever, cases) -> list[dict]:
    rows = []
    for case in cases:
        response = retriever.search(SearchRequest(case.query, FILTER, top_k=50, caller="evaluator"))
        ranked = list(dict.fromkeys(hit.document_id for hit in response.hits))[:10]
        rank = next((i for i, doc in enumerate(ranked, 1) if doc in case.relevant_document_ids), None)
        rows.append({"ranked_document_ids": ranked, "first_relevant_rank": rank,
                     "latency_ms": response.elapsed_ms})
    return rows


def summarize(cases, rows) -> dict:
    expected = [case.relevant_document_ids for case in cases]
    ranked = [row["ranked_document_ids"] for row in rows]
    overlaps = {k: [len(set(ids[:k]) & gt) for ids, gt in zip(ranked, expected)] for k in CUTOFFS}
    latency = [row["latency_ms"] for row in rows]
    existing = compute_metrics((ids, gt, ms, None) for ids, gt, ms in zip(ranked, expected, latency))
    return {
        "hit_rate": {k: fmean(n > 0 for n in overlaps[k]) for k in CUTOFFS},
        "recall": {k: fmean(n / len(gt) for n, gt in zip(overlaps[k], expected)) for k in CUTOFFS},
        "mrr_at_10": fmean(1 / rank if rank else 0 for rank in (row["first_relevant_rank"] for row in rows)),
        "ndcg_at_5": existing.ndcg_at_5,
        "mean_latency_ms": fmean(latency),
        "p95_latency_ms": existing.p95_latency_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--gt", type=Path, help="Human-reviewed GT JSONL with positive official document IDs")
    parser.add_argument("--dense-hybrid", action="store_true", help="Run optional Dense and Hybrid after BM25")
    parser.add_argument("--output", type=Path, required=True, help="New private directory outside the checkout")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("--output must be outside the checkout")

    settings = read_settings(args.env)
    print(f"Chroma {settings.host}:{settings.port}, collection {settings.collection}", flush=True)
    collection = ReadOnlyCollection(settings)
    snapshot = OfficialChromaChunkLoader(collection, collection_name=settings.collection).load()
    required = ("document_id", "source_id", "document_version", "title")
    for field in required:
        if any(not isinstance(c.metadata.get(field), str) or not c.metadata[field].strip()
               for c in snapshot.chunks):
            raise ValueError(f"Official Chroma snapshot has empty or missing {field}")
    doc_ids = {c.metadata["document_id"] for c in snapshot.chunks}

    frozen = FrozenLoader(snapshot)
    managers = {}
    build = {}
    for name, tokenizer in (("basic", basic_tokenize), ("kiwi", kiwi_tokenize)):
        manager = BM25IndexManager(frozen, tokenizer=tokenizer)
        try:
            state = manager.rebuild()
        except Exception as exc:
            raise RuntimeError(f"{name} index rebuild failed: {type(exc).__name__}") from exc
        if not (state.state == "ready" and state.ids_verified
                and state.snapshot_id == snapshot.snapshot_id
                and state.index_chunk_count == len(snapshot.chunk_ids)):
            raise RuntimeError(f"{name} did not verify against the shared snapshot")
        managers[name] = manager
        build[name] = {"state": state.state, "ids_verified": state.ids_verified,
                       "snapshot_id": state.snapshot_id, "chunks": state.index_chunk_count}

    if args.gt:
        cases = load_jsonl(args.gt)
        if not cases or any(case.scope is not KnowledgeScope.OFFICIAL or not case.relevant_document_ids
                            or not case.relevant_document_ids <= doc_ids for case in cases):
            raise ValueError("GT must contain positive official cases mapped to the Chroma snapshot")
        groups = {"reviewed_gt": cases}
    else:
        build_dir = args.data / "rag-build"
        cases = exploratory_cases(
            args.data / "faq.json",
            build_dir / "bm25-tokenization/manual_query_evaluation_template.jsonl",
            build_dir / "bm25-tokenizer-comparison/tokenizer_comparison_cases.jsonl",
            snapshot,
        )
        groups = {split: [case for case in cases if case.metadata["split"] == split]
                  for split in ("original", "synthetic")}

    # Warm both paths before timing. Alternate first searcher by question.
    for manager in managers.values():
        evaluate(manager, cases[:1])
    summary = {"collection": snapshot.collection, "total_chunks": snapshot.collection_count,
               "eligible_chunks": len(snapshot.chunks), "documents": len(doc_ids),
               "required_metadata_verified": list(required), "build": build, "groups": {}}
    details = []
    for split, group in groups.items():
        results = {name: [] for name in managers}
        for index, case in enumerate(group):
            order = tuple(managers) if index % 2 == 0 else tuple(reversed(managers))
            for name in order:
                results[name].extend(evaluate(managers[name], [case]))
        summary["groups"][split] = {
            "cases": len(group),
            "types": dict(Counter(case.metadata.get("variant", "reviewed") for case in group)),
            **{name: summarize(group, rows) for name, rows in results.items()},
        }
        divergences = Counter()
        for case, basic, kiwi in zip(group, results["basic"], results["kiwi"]):
            success = [row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 5
                       for row in (basic, kiwi)]
            outcome = ("both_hit" if success[0] else "both_miss")
            if success[0] != success[1]:
                outcome = "basic_only" if success[0] else "kiwi_only"
            divergences[outcome] += 1
            details.append({"case_id": case.case_id, "query": case.query, "scope": case.scope.value,
                            "relevant_document_ids": sorted(case.relevant_document_ids),
                            "metadata": dict(case.metadata), "basic": basic, "kiwi": kiwi,
                            "outcome_at_5": outcome})
        summary["groups"][split]["outcomes_at_5"] = dict(divergences)

    output.mkdir(mode=0o700)
    for name, content in (("summary.json", json.dumps(summary, ensure_ascii=False, indent=2)),
                          ("question-results.jsonl", "\n".join(json.dumps(row, ensure_ascii=False) for row in details))):
        (output / name).write_text(content + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if args.dense_hybrid:
        dense = OfficialKnowledgeSearchService(
            ChromaDenseRetriever(collection, BgeM3Embedder(settings.embedding_model))
        )
        hybrid = HybridRetriever(dense, managers["kiwi"])
        comparison = {}
        for name, retriever in (("dense", dense), ("dense_kiwi_rrf", hybrid)):
            evaluate(retriever, cases[:1])
            comparison[name] = {
                split: summarize(group, evaluate(retriever, group)) for split, group in groups.items()
            }
            print(json.dumps({name: comparison[name]}, ensure_ascii=False), flush=True)
            (output / "dense-hybrid-summary.json").write_text(
                json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
