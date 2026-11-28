"""Run the Agent's pre-generation nodes without starting the chat runtime."""

from __future__ import annotations

import argparse
import sys

from rag.scripts.demo_retrieval import ROOT, describe_error, display_text

FLAG_NAMES = (
    "has_individual_order_context",
    "is_sensitive",
    "is_safety_related",
    "is_urgent",
)


class ObservedOfficialSearch:
    def __init__(self, settings):
        self.settings = settings
        self.hits = ()
        self.called = False
        self.error = None

    def search_official(self, query: str, *, top_k: int):
        from app.ai.retrieval_adapter import OfficialRetrievalAdapter, OfficialRetrievalUnavailable

        try:
            adapter = OfficialRetrievalAdapter.connect(self.settings)
            self.called = True
            self.hits = adapter.search_official(query, top_k=top_k)
        except OfficialRetrievalUnavailable as error:
            self.error = error
            raise
        return self.hits


def run(args: argparse.Namespace) -> int:
    from app.ai.agent import (
        classify, retrieve_official_context, route_after_classify, route_after_retrieve,
    )
    from app.ai.guardrails import evaluate_input_guardrail

    state = {"inquiry_text": args.query}
    state.update({flag: getattr(args, flag) for flag in FLAG_NAMES if getattr(args, flag) is not None})
    print("========================================\neVOC Agent Routing Demo\n"
          "========================================")
    print(f"\n[INPUT]\n질문: {display_text(args.query)}")
    print("\n[STATE]")
    for flag in FLAG_NAMES:
        value = "미설정" if flag not in state else "true (수동 입력)"
        print(f"{flag}: {value}")

    updates = classify(state)
    state.update(updates)
    print("\n[CLASSIFY]\n분류 방식: 현재 classify 노드는 빈 딕셔너리를 반환")
    print("텍스트 기반 자동 분류: 없음 · 분기 단계에서 텍스트 가드레일 적용")
    print(f"State 변경: {list(updates) if updates else '없음'}")
    route = route_after_classify(state)
    guardrail = evaluate_input_guardrail(args.query)
    flags = [flag for flag in FLAG_NAMES if state.get(flag)]
    if guardrail.should_handoff:
        reason = f"{guardrail.reason_code} · {guardrail.reason}"
    elif flags and route == "handoff":
        reason = "수동 입력 State 플래그에 따른 이관"
    elif route == "handoff":
        reason = "Agent 이관 규칙"
    else:
        reason = "입력 가드레일 및 State 이관 조건 미충족"
    print(f"\n[ROUTING]\n선택된 경로: {route}\n판단 근거: {reason}")
    print(f"활성 플래그: {', '.join(flags) or '없음'}")
    print(f"검색 전 상담원 이관: {'YES' if route == 'handoff' else 'NO'}")
    print(f"\n[RETRIEVAL]\n검색 진입 여부: {'YES' if route == 'retrieve' else 'NO'}")
    if route != "retrieve" or not args.with_retrieval:
        print("검색 실제 호출: NO")
        return 0

    from app.core.config import get_settings
    from rag.app.retrieval.official import OfficialSearchSettings

    settings = get_settings()
    search = ObservedOfficialSearch(OfficialSearchSettings(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection=settings.chroma_official_collection,
        embedding_model=settings.rag_embedding_model,
    ))
    result = retrieve_official_context(state, search=search, top_k=settings.rag_top_k)
    print(f"검색 실제 호출: {'YES' if search.called else 'NO'}")
    print(f"전략: Dense · 공식 컬렉션: {display_text(settings.chroma_official_collection)}")
    next_route = route_after_retrieve({**state, **result})
    if result.get("retrieval_failed"):
        print(f"검색 실패 · 그래프의 다음 경로: {next_route}")
        if search.error is not None:
            describe_error(search.error)
        return 1

    for rank, hit in enumerate(search.hits, 1):
        print(f"{rank}위 | {display_text(hit.metadata.get('title') or '(제목 없음)')}")
        print(f"     chunk_id: {display_text(hit.chunk_id)}")
        print(f"     source_id: {display_text(hit.metadata.get('source_id') or '(없음)')}")
        print(f"     검색 점수: {hit.score:.8f}")
    context = result["context"]
    print(f"공식 Context 채택: {len(context.official_evidence)}개")
    print(f"그래프의 다음 경로: {next_route}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="eVOC Agent의 분류·분기와 선택적 공식 검색을 진단합니다.")
    parser.add_argument("--query", required=True, help="진단할 질문")
    parser.add_argument("--with-retrieval", action="store_true", help="retrieve 분기에서 실제 Dense 검색")
    for flag in FLAG_NAMES:
        parser.add_argument("--" + flag.replace("_", "-"), action="store_true", default=None,
                            help=f"Agent State의 {flag}를 수동으로 활성화")
    args = parser.parse_args(argv)
    if not args.query.strip():
        parser.error("--query에 질문을 입력하세요.")

    sys.path.insert(0, str(ROOT / "backend"))
    try:
        return run(args)
    except Exception as error:
        describe_error(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
