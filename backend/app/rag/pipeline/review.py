"""Apply explicit human review decisions before documents enter RAG indexing."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from .normalization import NormalizationError


ReviewStatus = Literal["APPROVED", "PENDING_REVIEW", "EXCLUDED"]
_VALID_STATUSES = {"APPROVED", "PENDING_REVIEW", "EXCLUDED"}


@dataclass(frozen=True)
class ReviewDecision:
    """A traceable human decision for one prepared document."""

    source_id: str
    review_status: ReviewStatus
    reason: str
    reviewed_by: str
    reviewed_at: str

    def as_row(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "review_status": self.review_status,
            "reason": self.reason,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }


def parse_review_decision(row: Mapping[str, Any]) -> ReviewDecision:
    def required(field: str) -> str:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise NormalizationError(f"missing required review field {field}")
        return value.strip()

    status = required("review_status")
    if status not in _VALID_STATUSES:
        raise NormalizationError("unsupported review_status")
    reviewed_at = row.get("reviewed_at")
    if reviewed_at is None:
        reviewed_at = datetime.now(UTC).isoformat()
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise NormalizationError("reviewed_at must be a non-empty string")
    return ReviewDecision(
        source_id=required("source_id"),
        review_status=status,  # type: ignore[arg-type]
        reason=required("reason"),
        reviewed_by=required("reviewed_by"),
        reviewed_at=reviewed_at.strip(),
    )


def parse_review_decisions(rows: Iterable[Mapping[str, Any]]) -> list[ReviewDecision]:
    decisions: list[ReviewDecision] = []
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        decision = parse_review_decision(row)
        if decision.source_id in seen:
            raise NormalizationError(f"duplicate review decision at line {line_number}")
        seen.add(decision.source_id)
        decisions.append(decision)
    return decisions


def apply_review_decisions(
    ingestion_rows: Iterable[Mapping[str, Any]],
    manifest_rows: Iterable[Mapping[str, Any]],
    decisions: Iterable[ReviewDecision],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return approved ingestion rows and an updated, auditable manifest.

    A decision cannot approve an inactive or non-draftable document.  Unknown
    source IDs are errors so a misspelled review record can never be ignored.
    """
    documents = {str(row.get("source_id", "")).strip(): dict(row) for row in ingestion_rows}
    manifests = {str(row.get("source_id", "")).strip(): dict(row) for row in manifest_rows}
    if "" in documents or "" in manifests or set(documents) != set(manifests):
        raise NormalizationError("ingestion rows and manifest rows must have matching source_id values")

    for decision in decisions:
        metadata = manifests.get(decision.source_id)
        if metadata is None:
            raise NormalizationError(f"review decision references unknown source_id {decision.source_id}")
        raw_status = metadata.get("raw_status")
        allowed_use = metadata.get("allowed_use")
        if decision.review_status == "APPROVED" and raw_status != "ACTIVE":
            raise NormalizationError("inactive document cannot be approved")
        if decision.review_status == "APPROVED" and allowed_use != "DRAFT_ONLY":
            raise NormalizationError("non-draftable document cannot be approved")
        metadata.update(decision.as_row())
        if decision.review_status == "EXCLUDED":
            metadata["allowed_use"] = "NOT_ALLOWED"

    approved_ids = [
        source_id
        for source_id, metadata in manifests.items()
        if metadata.get("raw_status") == "ACTIVE"
        and metadata.get("review_status") == "APPROVED"
        and metadata.get("allowed_use") == "DRAFT_ONLY"
    ]
    return [documents[source_id] for source_id in approved_ids], list(manifests.values())
