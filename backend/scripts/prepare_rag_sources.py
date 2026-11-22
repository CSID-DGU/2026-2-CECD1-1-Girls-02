"""Prepare approved local FAQ/Markdown sources for the separate RAG ingestion step.

Examples:
  python scripts/prepare_rag_sources.py --source company-faq --input /private/faq.json \
    --output /private/faq.ingestion.jsonl --manifest /private/faq.manifest.jsonl
  python scripts/prepare_rag_sources.py --source policy --business-domain COUPON \
    --input /private/coupon.md --output /private/coupon.ingestion.jsonl \
    --manifest /private/coupon.manifest.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.pipeline.company_sources import (
    prepare_company_faq_rows,
    prepare_markdown_file,
    policy_profile,
)
from app.rag.pipeline.normalization import NormalizationError, write_jsonl


def _load_company_faq(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise NormalizationError("company FAQ input must be valid JSON") from error
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise NormalizationError("company FAQ input must contain an items array of objects")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare private source files for review; does not embed or index documents."
    )
    parser.add_argument("--source", required=True, choices=("company-faq", "policy", "guide", "franchise"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Safe ingestion JSONL output")
    parser.add_argument("--manifest", required=True, type=Path, help="Review and policy metadata JSONL")
    parser.add_argument("--rejects", type=Path, help="Optional rejection diagnostics JSONL")
    parser.add_argument("--business-domain", default="GENERAL")
    parser.add_argument("--document-version", default="unspecified")
    args = parser.parse_args()

    if args.source == "company-faq":
        documents, rejected = prepare_company_faq_rows(_load_company_faq(args.input))
    else:
        documents = prepare_markdown_file(
            args.input,
            source_kind=args.source,
            business_domain=args.business_domain,
            document_version=args.document_version,
        )
        rejected = []

    write_jsonl(args.output, (document.as_ingestion_row() for document in documents))
    write_jsonl(args.manifest, (document.as_manifest_row() for document in documents))
    if args.rejects:
        write_jsonl(args.rejects, rejected)
    print(f"prepared={len(documents)} rejected={len(rejected)} status=PENDING_REVIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
