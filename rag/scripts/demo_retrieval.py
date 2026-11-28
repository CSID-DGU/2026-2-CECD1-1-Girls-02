"""Inspect official retrieval and Agent evidence in a read-only local CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import sys
import unicodedata

from rag.app.ingestion import mask_pii
from rag.app.retrieval.bm25 import basic_tokenize
from rag.app.retrieval.bm25_chroma import BM25IndexManager, OfficialChromaChunkLoader
from rag.app.retrieval.contracts import KnowledgeScope, Retriever, SearchFilter, SearchRequest, SearchResponse
from rag.app.retrieval.hybrid import DEFAULT_RRF_K, HybridRetriever, reciprocal_rank_score
from rag.app.retrieval.official import OfficialKnowledgeSearchService, OfficialSearchSettings

ROOT = Path(__file__).resolve().parents[2]
FILTER = SearchFilter(scope=KnowledgeScope.OFFICIAL)
RRF_K = DEFAULT_RRF_K
CANDIDATE_K = 10


@dataclass
class ObservedRetriever:
    retriever: Retriever
    result: SearchResponse | None = None

    def search(self, request: SearchRequest) -> SearchResponse:
        self.result = self.retriever.search(request)
        return self.result

    def captured(self) -> SearchResponse:
        if self.result is None:
            raise RuntimeError("검색기 호출 결과가 없습니다.")
        return self.result


def display_text(value: object) -> str:
    masked, _ = mask_pii(str(value))
    from app.ai.privacy import redact_pii

    return "".join(
        ch for ch in redact_pii(masked)
        if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"}
    )


def preview(value: str, full_text: bool) -> str:
    text = display_text(value)
    if full_text:
        return text
    return text if len(text) <= 200 else text[:199] + "…"


def rrf_details(
    chunk_id: str, score: float, dense_ranks: dict[str, int], bm25_ranks: dict[str, int]
) -> str:
    dense_rank = dense_ranks.get(chunk_id)
    bm25_rank = bm25_ranks.get(chunk_id)
    ranks = [rank for rank in (dense_rank, bm25_rank) if rank is not None]
    calculated = sum(reciprocal_rank_score(rank, rrf_k=RRF_K) for rank in ranks)
    if not ranks or not math.isclose(score, calculated, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError("Hybrid 실제 점수와 RRF 재계산 결과가 일치하지 않습니다.")
    terms = " + ".join(f"1 / ({RRF_K} + {rank})" for rank in ranks)
    return (f"Dense 순위: {dense_rank or '후보 없음'} | BM25 순위: {bm25_rank or '후보 없음'}\n"
            f"     RRF 계산: {terms} = {calculated:.8f} (일치)")


def emit_results(
    label: str, limit: int, response: SearchResponse, full_text: bool,
    candidates: tuple[SearchResponse, SearchResponse] | None = None,
) -> None:
    print(f"\n[{label} TOP-{limit}] {len(response.hits)}개 · {response.elapsed_ms:.2f} ms")
    if not response.hits:
        print("검색 결과가 없습니다.")
    ranks = tuple({hit.chunk_id: rank for rank, hit in enumerate(result.hits, 1)}
                  for result in candidates) if candidates else None
    for rank, hit in enumerate(response.hits, 1):
        print(f"{rank}위 | {display_text(hit.metadata.get('title') or '(제목 없음)')}")
        print(f"     document_id: {display_text(hit.document_id)}")
        print(f"     chunk_id: {display_text(hit.chunk_id)}")
        print(f"     source_id: {display_text(hit.metadata.get('source_id') or '(없음)')}")
        score_label = "RRF 점수" if ranks is not None else "검색 점수"
        print(f"     {score_label}: {hit.score:.8f}")
        if ranks is not None:
            print(f"     {rrf_details(hit.chunk_id, hit.score, *ranks)}")
        print(f"     본문: {preview(hit.text, full_text)}")


def emit_context(chunks, top_k: int) -> None:
    from app.ai.context import build_official_context

    context = build_official_context(chunks, max_chunks=top_k)
    documents = {chunk.metadata.get("document_id") for chunk in chunks
                 if chunk.chunk_id in context.selected_chunk_ids}
    print(f"\n[공식 LLM 근거] 문서 {len(documents)}개 · 청크 {len(context.official_evidence)}개")
    for evidence in context.official_evidence:
        print(f"- {display_text(evidence.title)} | source_id: {display_text(evidence.source_id)}")
        print(f"  {display_text(evidence.excerpt)}")
    skipped = set(context.skipped_chunk_ids)
    for chunk in chunks:
        if chunk.chunk_id not in skipped:
            continue
        # Ask the same builder whether this chunk is eligible without preceding evidence.
        eligible = build_official_context([chunk], max_chunks=1, max_characters=max(1, len(chunk.text)))
        reason = ("근거 개수 또는 본문 길이 한도" if eligible.official_evidence
                  else "공식 근거 조건 불충족 또는 출처 ID·제목·본문 누락")
        print(f"- 제외 {display_text(chunk.chunk_id)} | {reason}")


def make_searchers(settings: OfficialSearchSettings, strategy: str):
    import chromadb
    from chromadb.config import Settings as ChromaClientSettings

    def client_factory(*, host: str, port: int):
        return chromadb.HttpClient(
            host=host, port=port, settings=ChromaClientSettings(anonymized_telemetry=False)
        )

    dense = bm25 = None
    if strategy in {"dense", "hybrid", "all"}:
        dense = ObservedRetriever(OfficialKnowledgeSearchService.connect(settings, client_factory=client_factory))
        print("Dense 검색 연결 확인", flush=True)
    if strategy in {"bm25", "hybrid", "all"}:
        loader = OfficialChromaChunkLoader.connect(settings, client_factory=client_factory)
        manager = BM25IndexManager(loader, tokenizer=basic_tokenize)
        status = manager.rebuild()
        if status.state != "ready" or not status.ids_verified:
            raise RuntimeError("Basic BM25 인덱스 준비 상태를 확인하지 못했습니다.")
        print(f"공식 승인 청크: {status.loaded_chunk_count}/{status.collection_chunk_count}개"
              f" · Basic BM25 {status.state} · 인덱스 {status.index_chunk_count}개", flush=True)
        bm25 = ObservedRetriever(manager)
    elif strategy == "dense":
        loader = OfficialChromaChunkLoader.connect(settings, client_factory=client_factory)
        snapshot = loader.load()
        print(f"공식 승인 청크: {len(snapshot.chunks)}/{snapshot.collection_count}개", flush=True)
    return dense, bm25


def run_question(query: str, args, dense, bm25, hybrid_adapter, hybrid) -> None:
    print(f"\n질문: {display_text(query)}", flush=True)
    direct_k = max(CANDIDATE_K, args.top_k) if args.strategy == "all" else args.top_k
    request = SearchRequest(query, FILTER, top_k=direct_k, caller="retrieval_demo")
    if args.strategy in {"dense", "all"}:
        emit_results("DENSE", direct_k, dense.search(request), args.show_full_text)
    if args.strategy in {"bm25", "all"}:
        emit_results("BASIC BM25", direct_k, bm25.search(request), args.show_full_text)
    if hybrid_adapter is not None:
        chunks = hybrid_adapter.search_official(query, top_k=args.top_k)
        emit_results("HYBRID RRF", args.top_k, hybrid.captured(), args.show_full_text,
                     candidates=(dense.captured(), bm25.captured()))
        emit_context(chunks, args.top_k)


def describe_error(error: Exception) -> None:
    parts = []
    current = error
    while current is not None:
        parts.append(f"{type(current).__name__}: {display_text(current)}")
        current = current.__cause__
    print("오류: " + " → ".join(parts), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="eVOC 공식 FAQ 검색 결과를 읽기 전용으로 확인합니다.")
    parser.add_argument("--query", help="한 질문을 검색한 뒤 종료")
    parser.add_argument("--top-k", type=int, default=5,
                        help="최종 결과 수 (1~50). all의 Dense·BM25는 최소 10개")
    parser.add_argument("--show-full-text", action="store_true", help="검색 결과의 청크 본문 전체 표시")
    parser.add_argument("--strategy", choices=("dense", "bm25", "hybrid", "all"), default="all")
    args = parser.parse_args(argv)
    if not 1 <= args.top_k <= 50:
        parser.error("--top-k 값은 1~50이어야 합니다.")
    if args.query is not None and not args.query.strip():
        parser.error("--query에 질문을 입력하세요.")

    sys.path.insert(0, str(ROOT / "backend"))
    from app.ai.retrieval_adapter import OfficialRetrievalAdapter
    from dotenv import dotenv_values

    try:
        values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
        settings = OfficialSearchSettings.from_env({**values, **os.environ})
        print("========================================\neVOC RAG Retrieval Demo\n"
              "========================================", flush=True)
        print(f"검색 전략: {args.strategy} · Hybrid는 Dense + Basic BM25 RRF (1:1, k={RRF_K})")
        print(f"공식 Collection: {settings.collection} ({settings.host}:{settings.port})", flush=True)
        dense, bm25 = make_searchers(settings, args.strategy)
        hybrid = hybrid_adapter = None
        if args.strategy in {"all", "hybrid"}:
            hybrid = ObservedRetriever(HybridRetriever(
                dense, bm25, rrf_k=RRF_K, dense_candidate_k=CANDIDATE_K, bm25_candidate_k=CANDIDATE_K
            ))
            hybrid_adapter = OfficialRetrievalAdapter(hybrid)
        if args.query is not None:
            run_question(args.query.strip(), args, dense, bm25, hybrid_adapter, hybrid)
            return 0
    except Exception as error:
        describe_error(error)
        return 1

    print("\n질문을 입력하세요. 종료하려면 exit 또는 quit을 입력하세요.")
    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if query.casefold() in {"exit", "quit"}:
            return 0
        if query:
            try:
                run_question(query, args, dense, bm25, hybrid_adapter, hybrid)
            except Exception as error:
                describe_error(error)
            except KeyboardInterrupt:
                print()
                return 0


if __name__ == "__main__":
    raise SystemExit(main())
