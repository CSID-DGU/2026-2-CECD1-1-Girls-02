"""Normalize private FAQ and VOC exports before RAG ingestion.

The input exports must remain outside version control.  This module emits the
minimal JSONL contract consumed by ``rag/scripts/ingest_jsonl.py`` and masks
direct personal identifiers before any text is persisted as an artifact.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
from typing import Any, Literal


FAQ_SOURCE_TYPE = "official"
VOC_SOURCE_TYPE = "voc"

_WHITESPACE = re.compile(r"[ \t\r\n]+")
_HTML_TAG = re.compile(r"<[^>]+>")
_PII_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+82[- ]?)?0?1[0-9][- ]?\d{3,4}[- ]?\d{4}(?!\d)")),
    ("resident_id", re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)")),
    ("card", re.compile(r"(?<!\d)(?:\d{4}[- ]?){3}\d{4}(?!\d)")),
)


class NormalizationError(ValueError):
    """Raised when a source row cannot safely become a RAG record."""


@dataclass(frozen=True)
class NormalizedRecord:
    """The approved, source-neutral contract passed to the ingestion step."""

    source_id: str
    title: str
    text: str
    document_version: str
    source_type: Literal["official", "voc"]
    category: str | None = None
    source_url: str | None = None
    published_at: str | None = None

    def as_ingestion_row(self) -> dict[str, str]:
        row = {
            "source_id": self.source_id,
            "title": self.title,
            "text": self.text,
            "document_version": self.document_version,
            "source_type": self.source_type,
        }
        for field_name in ("category", "source_url", "published_at"):
            value = getattr(self, field_name)
            if value:
                row[field_name] = value
        return row


def _value(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _clean_text(value: str) -> str:
    text = html.unescape(_HTML_TAG.sub(" ", value))
    for label, pattern in _PII_PATTERNS:
        text = pattern.sub(f"[{label.upper()}_REDACTED]", text)
    return _WHITESPACE.sub(" ", text).strip()


def _required(row: Mapping[str, Any], label: str, *keys: str) -> str:
    value = _value(row, *keys)
    if not value:
        raise NormalizationError(f"missing required {label}")
    cleaned = _clean_text(value)
    if not cleaned:
        raise NormalizationError(f"empty {label} after normalization")
    return cleaned


def _optional(row: Mapping[str, Any], *keys: str) -> str | None:
    value = _value(row, *keys)
    return _clean_text(value) if value else None


def _version(row: Mapping[str, Any]) -> str:
    return _optional(row, "document_version", "version", "updated_at", "updatedAt") or "unspecified"


def normalize_faq_record(row: Mapping[str, Any]) -> NormalizedRecord:
    """Convert one FAQ export row into an official-knowledge ingestion row."""
    source_id = _required(row, "FAQ id", "faq_id", "id", "source_id", "FAQ_ID")
    question = _required(row, "FAQ question", "question", "inquiry", "title", "질문")
    answer = _required(row, "FAQ answer", "answer", "content", "response", "답변")
    category = _optional(row, "category", "category_name", "분류")
    return NormalizedRecord(
        source_id=f"faq:{source_id}",
        title=f"FAQ: {question}",
        text=f"질문: {question}\n답변: {answer}",
        document_version=_version(row),
        source_type=FAQ_SOURCE_TYPE,
        category=category,
        source_url=_optional(row, "source_url", "url", "link"),
        published_at=_optional(row, "published_at", "publishedAt", "created_at"),
    )


def normalize_voc_record(row: Mapping[str, Any]) -> NormalizedRecord:
    """Convert one VOC export row into an agent-reference-only ingestion row."""
    source_id = _required(row, "VOC id", "voc_id", "case_id", "ticket_id", "id", "source_id")
    inquiry = _required(row, "VOC inquiry", "inquiry", "question", "content", "문의내용")
    resolution = _optional(row, "resolution", "answer", "response", "handling_result", "처리내용")
    category = _optional(row, "category", "category_name", "분류")
    title = f"VOC: {category or '미분류'} 사례"
    text_parts = [f"고객 문의: {inquiry}"]
    if resolution:
        text_parts.append(f"처리 결과: {resolution}")
    return NormalizedRecord(
        source_id=f"voc:{source_id}",
        title=title,
        text="\n".join(text_parts),
        document_version=_version(row),
        source_type=VOC_SOURCE_TYPE,
        category=category,
        published_at=_optional(row, "closed_at", "resolved_at", "created_at"),
    )


def normalize_rows(
    rows: Iterable[Mapping[str, Any]], source_kind: Literal["faq", "voc"]
) -> tuple[list[NormalizedRecord], list[dict[str, str | int]]]:
    """Return safe rows and rejection diagnostics without retaining raw content."""
    converter = normalize_faq_record if source_kind == "faq" else normalize_voc_record
    accepted: list[NormalizedRecord] = []
    rejected: list[dict[str, str | int]] = []
    seen_ids: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        try:
            record = converter(row)
            if record.source_id in seen_ids:
                raise NormalizationError("duplicate source id")
            seen_ids.add(record.source_id)
            accepted.append(record)
        except NormalizationError as error:
            rejected.append({"line": line_number, "reason": str(error)})
    return accepted, rejected


def read_jsonl(path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise NormalizationError(f"invalid JSON at line {line_number}") from error
            if not isinstance(value, Mapping):
                raise NormalizationError(f"JSON object expected at line {line_number}")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize private FAQ/VOC JSONL for RAG ingestion.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source", required=True, choices=("faq", "voc"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rejects", required=True, type=Path)
    args = parser.parse_args()
    records, rejected = normalize_rows(read_jsonl(args.input), args.source)
    processed_at = datetime.now(UTC).isoformat()
    write_jsonl(args.output, (record.as_ingestion_row() for record in records))
    write_jsonl(args.rejects, ({**item, "processed_at": processed_at} for item in rejected))
    print(f"accepted={len(records)} rejected={len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
