"""Export a private, human-readable review queue for prepared RAG documents.

The output contains document content and must stay under backend/data/private/
or another ignored local path.  It is a review aid only; reviewers record final
decisions in a separate JSONL file consumed by apply_rag_reviews.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSON object expected at line {line_number} in {path.name}")
            rows.append(value)
    return rows


def build_review_queue(
    documents: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    *,
    category: str | None = None,
) -> str:
    document_by_id = {str(row.get("source_id", "")): row for row in documents}
    candidates = [
        row
        for row in manifests
        if row.get("raw_status") == "ACTIVE"
        and row.get("review_status") == "PENDING_REVIEW"
        and (category is None or row.get("category_code") == category)
    ]
    lines = [
        "# RAG 문서 검수 큐",
        "",
        f"- 검수 대상: {len(candidates)}건",
        "- 승인 기준: 활성 공식 문서, 답변 범위 명확, 개인·주문 처리 정보 없음",
        "- 결정: `APPROVED` / `PENDING_REVIEW` / `EXCLUDED`",
        "- 이 파일은 비공개 검수 보조 자료이며 Git에 커밋하지 않습니다.",
        "",
    ]
    for index, metadata in enumerate(candidates, start=1):
        source_id = str(metadata["source_id"])
        document = document_by_id.get(source_id)
        if document is None:
            raise ValueError(f"manifest source_id not found in documents: {source_id}")
        lines.extend(
            [
                f"## {index}. {source_id}",
                "",
                f"- 카테고리: `{metadata.get('category_code', 'GENERAL')}`",
                f"- 문서 유형: `{metadata.get('doc_type', '')}`",
                f"- 권한: `{metadata.get('authority_level', '')}`",
                f"- 버전: `{metadata.get('document_version', '')}`",
                f"- 제목: {document.get('title', '')}",
                "",
                "### 검수할 원문",
                "",
                str(document.get("text", "")),
                "",
                "### 검수 체크",
                "",
                "- [ ] 공식 FAQ/정책이며 현재 활성 문서인가?",
                "- [ ] 질문과 답변의 범위·조건·예외가 충분히 명확한가?",
                "- [ ] 특정 고객·주문·매장·개인정보 처리 내용이 없는가?",
                "- [ ] 최신성 확인이 필요한 일시적 안내가 아닌가?",
                "- [ ] 결정: APPROVED / PENDING_REVIEW / EXCLUDED",
                "- 사유:",
                "",
            ]
        )
    return "\n".join(lines)


def build_voc_review_queue(cases: list[dict[str, Any]]) -> str:
    """Render only privacy-prepared, agent-only VOC cases for human review."""
    candidates = [case for case in cases if case.get("case_status") == "READY_FOR_REVIEW"]
    lines = [
        "# VOC 격리 검수 큐",
        "",
        f"- 검수 대상: {len(candidates)}건",
        "- 용도: 관리자 분석·상담원 참고 전용입니다. 고객 자동답변 근거로 승인하지 않습니다.",
        "- 제외된 사례는 개인정보·개별 주문·안전/법적 이슈·처리 결과 누락으로 원문을 표시하지 않습니다.",
        "- 결정: `READY_FOR_REVIEW` / `EXCLUDED`",
        "- 이 파일은 비공개 검수 보조 자료이며 Git에 커밋하지 않습니다.",
        "",
    ]
    for index, case in enumerate(candidates, start=1):
        lines.extend(
            [
                f"## {index}. {case.get('source_id', '')}",
                "",
                f"- 분류: `{case.get('category_path', 'GENERAL')}`",
                f"- 원본 갱신 시각: `{case.get('source_updated_at', '')}`",
                f"- 제목: {case.get('title', '')}",
                "",
                "### 비식별화된 사례",
                "",
                str(case.get("text", "")),
                "",
                "### 검수 체크",
                "",
                "- [ ] 직접 식별자·주문/계정 정보가 남아 있지 않은가?",
                "- [ ] 안전·법적·긴급 민원에 해당하지 않는가?",
                "- [ ] 관리자 분석 또는 상담원 참고에만 적합한가?",
                "- [ ] 결정: READY_FOR_REVIEW / EXCLUDED",
                "- 사유:",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a private Markdown review queue.")
    parser.add_argument("--documents", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--category", help="Optional normalized category, e.g. MEMBERSHIP")
    parser.add_argument("--voc", action="store_true", help="Render a prepared VOC quarantine queue.")
    args = parser.parse_args()

    if args.voc:
        if args.manifest or args.category:
            parser.error("--voc does not accept --manifest or --category")
        queue = build_voc_review_queue(_read_jsonl(args.documents))
    else:
        if args.manifest is None:
            parser.error("--manifest is required unless --voc is used")
        queue = build_review_queue(
            _read_jsonl(args.documents),
            _read_jsonl(args.manifest),
            category=args.category,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(queue, encoding="utf-8", newline="\n")
    print(f"review_queue_written={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
