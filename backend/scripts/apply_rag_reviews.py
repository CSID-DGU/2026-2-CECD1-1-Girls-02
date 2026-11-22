"""Create approved-only RAG ingestion input from human review decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.pipeline.normalization import NormalizationError, write_jsonl
from app.rag.pipeline.review import apply_review_decisions, parse_review_decisions


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise NormalizationError(f"invalid JSONL at line {line_number} in {path.name}") from error
            if not isinstance(row, dict):
                raise NormalizationError(f"JSON object expected at line {line_number} in {path.name}")
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply human review decisions before RAG indexing.")
    parser.add_argument("--documents", required=True, type=Path, help="Prepared ingestion JSONL")
    parser.add_argument("--manifest", required=True, type=Path, help="Prepared review metadata JSONL")
    parser.add_argument("--decisions", required=True, type=Path, help="Human review decision JSONL")
    parser.add_argument("--approved-output", required=True, type=Path)
    parser.add_argument("--updated-manifest", required=True, type=Path)
    args = parser.parse_args()

    approved, updated_manifest = apply_review_decisions(
        _read_jsonl(args.documents),
        _read_jsonl(args.manifest),
        parse_review_decisions(_read_jsonl(args.decisions)),
    )
    write_jsonl(args.approved_output, approved)
    write_jsonl(args.updated_manifest, updated_manifest)
    print(f"approved={len(approved)} manifest_records={len(updated_manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
