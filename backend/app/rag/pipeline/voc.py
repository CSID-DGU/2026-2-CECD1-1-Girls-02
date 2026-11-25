"""Privacy-first preparation of historical VOC cases.

VOC is never emitted as official knowledge and must not be used for customer
answer drafts.  The output is a quarantined review artifact for a later,
agent-only workflow.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Literal

from .normalization import NormalizationError, _clean_text, _optional, _required


_ORDER_OR_ACCOUNT = re.compile(
    r"(?i)(?:주문\s*(?:번호|내역)?|order\s*(?:id|number|no\.?)?|회원\s*(?:번호|id)?|mb\s*id)\s*[:#]?\s*[a-z0-9_-]{3,}"
)
_EMAIL = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+82[-\s]?)?0?1[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)")
_HIGH_RISK_TERMS = ("이물질", "식중독", "장염", "상해", "응급", "소송", "법적", "경찰")
_ORDER_TERMS = ("주문", "결제", "배달", "취소", "환불")


@dataclass(frozen=True)
class PreparedVocCase:
    """A non-authoritative case; this object has no customer-draft eligibility."""

    source_id: str
    title: str
    text: str | None
    category_path: str
    case_status: Literal["READY_FOR_REVIEW", "EXCLUDED"]
    exclusion_reason: str | None
    source_updated_at: str | None

    def as_quarantine_row(self) -> dict[str, str]:
        """Return only fields that are approved for the isolated VOC store."""
        row = {
            "source_id": self.source_id,
            "source_type": "voc",
            # This corpus is for an administrator/agent's case-reference view.
            # It is deliberately not eligible as evidence for a customer draft.
            "usage_scope": "AGENT_REFERENCE_ONLY",
            "allowed_use": "AGENT_REFERENCE_ONLY",
            "category_path": self.category_path,
            "case_status": self.case_status,
            "exclusion_reason": self.exclusion_reason or "",
            "source_updated_at": self.source_updated_at or "",
            "document_version": self.source_updated_at or "voc-quarantined-v1",
            "doc_type": "VOC_CASE",
        }
        if self.text:
            row["title"] = self.title
            row["text"] = self.text
        return row


def _case_id(source_name: str, raw_id: str) -> str:
    """Avoid placing a source-system ticket ID in the prepared artifact."""
    digest = sha256(f"{source_name}:{raw_id}".encode("utf-8")).hexdigest()[:20]
    return f"voc:{source_name}:{digest}"


def _contains_high_risk(text: str, category_path: str) -> bool:
    combined = f"{text} {category_path}"
    return any(term in combined for term in _HIGH_RISK_TERMS)


def _contains_order_context(text: str, category_path: str) -> bool:
    combined = f"{text} {category_path}"
    return bool(_ORDER_OR_ACCOUNT.search(combined)) or any(term in combined for term in _ORDER_TERMS)


def _mask_direct_identifiers(text: str) -> str:
    normalized = text.replace("[EMAIL_REDACTED]", "[REDACTED_EMAIL]").replace(
        "[PHONE_REDACTED]", "[REDACTED_PHONE]"
    )
    masked = _EMAIL.sub("[REDACTED_EMAIL]", normalized)
    return _PHONE.sub("[REDACTED_PHONE]", masked)


def prepare_voc_case(row: Mapping[str, Any], *, source_name: str) -> PreparedVocCase:
    """Prepare one VOC row using an allow-list of non-identity fields only.

    Deliberately ignored source fields include writerName, email, phoneNumber,
    mbId, orderInfo, orderedMenu, storeCode, storeName, memo, and fileInfos.
    """
    raw_id = _required(row, "VOC id", "id")
    title = _required(row, "VOC title", "title")
    inquiry = _required(row, "VOC content", "content")
    resolution = _optional(row, "answer")
    category_path = _optional(row, "categoryPath") or "GENERAL"
    source_id = _case_id(source_name, raw_id)
    safe_title = _mask_direct_identifiers(_clean_text(title))
    safe_inquiry = _mask_direct_identifiers(
        _ORDER_OR_ACCOUNT.sub("[REDACTED_ORDER_OR_ACCOUNT]", _clean_text(inquiry))
    )
    safe_resolution = (
        _mask_direct_identifiers(_ORDER_OR_ACCOUNT.sub("[REDACTED_ORDER_OR_ACCOUNT]", _clean_text(resolution)))
        if resolution
        else None
    )

    if not safe_resolution:
        return PreparedVocCase(
            source_id, safe_title, None, category_path, "EXCLUDED", "missing resolution", _optional(row, "modifiedTime")
        )
    case_text = f"문의 요약: {safe_inquiry}\n처리 요약: {safe_resolution}"
    if _contains_high_risk(case_text, category_path):
        return PreparedVocCase(
            source_id, safe_title, None, category_path, "EXCLUDED", "safety or legal risk", _optional(row, "modifiedTime")
        )
    if _contains_order_context(case_text, category_path):
        return PreparedVocCase(
            source_id, safe_title, None, category_path, "EXCLUDED", "individual order or account context", _optional(row, "modifiedTime")
        )
    return PreparedVocCase(
        source_id, safe_title, case_text, category_path, "READY_FOR_REVIEW", None, _optional(row, "modifiedTime")
    )


def prepare_voc_rows(
    rows: Iterable[Mapping[str, Any]], *, source_name: str
) -> tuple[list[PreparedVocCase], list[dict[str, str | int]]]:
    """Prepare cases without exposing raw rejected text in diagnostics."""
    cases: list[PreparedVocCase] = []
    rejected: list[dict[str, str | int]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        try:
            case = prepare_voc_case(row, source_name=source_name)
            if case.source_id in seen:
                raise NormalizationError("duplicate VOC id")
            seen.add(case.source_id)
            cases.append(case)
        except NormalizationError as error:
            rejected.append({"line": line_number, "reason": str(error)})
    return cases, rejected
