"""Company-source adapters and eligibility rules for the RAG ingestion pipeline.

This module intentionally prepares documents only.  It does not embed or
index them: a reviewer must approve a document before it can become a
customer-answer draft source.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Literal

from .normalization import NormalizationError, _clean_text, _optional, _required


ReviewStatus = Literal["APPROVED", "PENDING_REVIEW", "EXCLUDED"]
RawStatus = Literal["ACTIVE", "INACTIVE"]
AllowedUse = Literal["DRAFT_ONLY", "AGENT_DRAFT_ONLY", "HANDOFF_CONTEXT_ONLY", "NOT_ALLOWED"]
AuthorityLevel = Literal["PRIMARY_POLICY", "OFFICIAL_FAQ", "SUPPORTING_GUIDE"]

_CATEGORY_CODES = {
    "멤버십": "MEMBERSHIP",
    "온라인주문": "ORDER",
    "주문": "ORDER",
    "단체주문": "ORDER",
    "쿠폰 및 상품권": "COUPON",
    "제휴할인": "COUPON",
    "제품": "PRODUCT",
    "배달 관련": "DELIVERY",
}
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SANITIZED_SUPPORT_PHONE = re.compile(r"(?<!\d)070[-\s]?(?:\d{3,4}|\*{3,4})[-\s]?\d{4}(?!\d)")
_BRAND_ALIAS = re.compile(r"pizzaalvolo|피자알볼로", re.IGNORECASE)


@dataclass(frozen=True)
class SourceProfile:
    """Policy assigned to a source before its contents are read."""

    doc_type: Literal["FAQ", "POLICY", "GUIDE"]
    authority_level: AuthorityLevel
    allowed_use: AllowedUse
    business_domain: str


@dataclass(frozen=True)
class PreparedDocument:
    """A sanitized document plus the review gates needed by later stages."""

    source_id: str
    title: str
    text: str
    document_version: str
    source_type: Literal["official"]
    category_code: str
    raw_status: RawStatus
    review_status: ReviewStatus
    doc_type: Literal["FAQ", "POLICY", "GUIDE"]
    trust_level: Literal["OFFICIAL"]
    allowed_use: AllowedUse
    authority_level: AuthorityLevel
    business_domain: str
    source_updated_at: str | None = None

    def as_ingestion_row(self) -> dict[str, str]:
        """The safe, legacy-compatible row consumed by the chunking adapter."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "text": self.text,
            "document_version": self.document_version,
            "source_type": self.source_type,
            "category": self.category_code,
        }

    def as_manifest_row(self) -> dict[str, str]:
        """Audit metadata; keep this beside the ingestion row, never in raw input."""
        return {
            "source_id": self.source_id,
            "category_code": self.category_code,
            "raw_status": self.raw_status,
            "review_status": self.review_status,
            "doc_type": self.doc_type,
            "trust_level": self.trust_level,
            "allowed_use": self.allowed_use,
            "authority_level": self.authority_level,
            "business_domain": self.business_domain,
            "document_version": self.document_version,
            "source_updated_at": self.source_updated_at or "",
        }


def draft_eligible(document: PreparedDocument) -> bool:
    """Return whether a document is eligible to support an AI answer draft."""
    return (
        document.raw_status == "ACTIVE"
        and document.review_status == "APPROVED"
        and document.trust_level == "OFFICIAL"
        and document.allowed_use == "DRAFT_ONLY"
    )


def category_code(category_name: str | None) -> str:
    """Keep unknown categories searchable without falsely assigning a domain."""
    return _CATEGORY_CODES.get((category_name or "").strip(), "GENERAL")


def _sanitize_customer_facing_text(value: str) -> str:
    """Remove the supplied brand alias and normalize legacy support numbers."""
    without_brand = _BRAND_ALIAS.sub("pizza", value)
    return _SANITIZED_SUPPORT_PHONE.sub("070-0000-0000", without_brand)


def prepare_company_faq(row: Mapping[str, Any]) -> PreparedDocument:
    """Prepare a row from the company's FAQ export without using attachments."""
    external_id = _required(row, "FAQ id", "id")
    question = _sanitize_customer_facing_text(_required(row, "FAQ title", "title"))
    answer = _sanitize_customer_facing_text(_required(row, "FAQ content", "content"))
    active = row.get("active")
    if not isinstance(active, bool):
        raise NormalizationError("FAQ active must be a boolean")
    raw_status: RawStatus = "ACTIVE" if active else "INACTIVE"
    review_status: ReviewStatus = "PENDING_REVIEW" if active else "EXCLUDED"
    allowed_use: AllowedUse = "DRAFT_ONLY" if active else "NOT_ALLOWED"
    updated_at = _optional(row, "modifiedTime")
    return PreparedDocument(
        source_id=f"faq:{external_id}",
        title=f"FAQ: {question}",
        text=f"카테고리: {category_code(_optional(row, 'categoryName'))}\n질문: {question}\n답변: {answer}",
        document_version=updated_at or "unspecified",
        source_type="official",
        category_code=category_code(_optional(row, "categoryName")),
        raw_status=raw_status,
        review_status=review_status,
        doc_type="FAQ",
        trust_level="OFFICIAL",
        allowed_use=allowed_use,
        authority_level="OFFICIAL_FAQ",
        business_domain=category_code(_optional(row, "categoryName")),
        source_updated_at=updated_at,
    )


def prepare_company_faq_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[PreparedDocument], list[dict[str, str | int]]]:
    """Prepare FAQ rows and retain only line number/reason for rejected inputs."""
    documents: list[PreparedDocument] = []
    rejected: list[dict[str, str | int]] = []
    seen_ids: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        try:
            document = prepare_company_faq(row)
            if document.source_id in seen_ids:
                raise NormalizationError("duplicate FAQ id")
            seen_ids.add(document.source_id)
            documents.append(document)
        except NormalizationError as error:
            rejected.append({"line": line_number, "reason": str(error)})
    return documents, rejected


def policy_profile(source_kind: Literal["policy", "guide", "franchise"], business_domain: str) -> SourceProfile:
    """Return explicit source policy rather than inferring trust from file text."""
    if source_kind == "policy":
        return SourceProfile("POLICY", "PRIMARY_POLICY", "DRAFT_ONLY", business_domain)
    if source_kind == "guide":
        return SourceProfile("GUIDE", "SUPPORTING_GUIDE", "DRAFT_ONLY", business_domain)
    return SourceProfile("GUIDE", "SUPPORTING_GUIDE", "DRAFT_ONLY", "FRANCHISE")


def prepare_markdown_sections(
    text: str, *, source_name: str, profile: SourceProfile, document_version: str = "unspecified"
) -> list[PreparedDocument]:
    """Split a vetted Markdown source at H2 headings, retaining heading context."""
    cleaned_source_name = _sanitize_customer_facing_text(_clean_text(source_name))
    if not cleaned_source_name:
        raise NormalizationError("missing source name")
    matches = list(_H2.finditer(text))
    if not matches:
        raise NormalizationError("Markdown source must contain at least one H2 heading")
    document_key = sha256(cleaned_source_name.encode("utf-8")).hexdigest()[:12]
    documents: list[PreparedDocument] = []
    for index, match in enumerate(matches):
        section_title = _sanitize_customer_facing_text(_clean_text(match.group(1)))
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_body = _sanitize_customer_facing_text(_clean_text(text[match.end() : next_start]))
        if not section_body or section_title in {"목차", "히스토리"}:
            continue
        documents.append(
            PreparedDocument(
                source_id=f"policy:{document_key}:s{index:03d}",
                title=f"{cleaned_source_name} - {section_title}",
                text=f"문서: {cleaned_source_name}\n섹션: {section_title}\n내용: {section_body}",
                document_version=document_version,
                source_type="official",
                category_code=profile.business_domain,
                raw_status="ACTIVE",
                review_status="PENDING_REVIEW",
                doc_type=profile.doc_type,
                trust_level="OFFICIAL",
                allowed_use=profile.allowed_use,
                authority_level=profile.authority_level,
                business_domain=profile.business_domain,
            )
        )
    if not documents:
        raise NormalizationError("Markdown source has no usable sections")
    return documents


def prepare_markdown_file(
    path: Path, *, source_kind: Literal["policy", "guide", "franchise"], business_domain: str,
    document_version: str = "unspecified", source_name: str | None = None,
) -> list[PreparedDocument]:
    """Read an approved Markdown file; its path is never emitted as metadata."""
    return prepare_markdown_sections(
        path.read_text(encoding="utf-8"),
        source_name=source_name or path.stem,
        profile=policy_profile(source_kind, business_domain),
        document_version=document_version,
    )
