import pytest

from app.rag.pipeline.normalization import NormalizationError
from app.rag.pipeline.review import apply_review_decisions, parse_review_decisions


def _rows():
    documents = [
        {"source_id": "faq:1", "title": "활성 FAQ", "text": "내용"},
        {"source_id": "faq:2", "title": "비활성 FAQ", "text": "이력"},
    ]
    manifest = [
        {"source_id": "faq:1", "raw_status": "ACTIVE", "review_status": "PENDING_REVIEW", "allowed_use": "DRAFT_ONLY"},
        {"source_id": "faq:2", "raw_status": "INACTIVE", "review_status": "EXCLUDED", "allowed_use": "NOT_ALLOWED"},
    ]
    return documents, manifest


def test_approved_active_document_is_the_only_document_exported_for_indexing():
    documents, manifest = _rows()
    decisions = parse_review_decisions(
        [{"source_id": "faq:1", "review_status": "APPROVED", "reason": "current official FAQ", "reviewed_by": "sophie-24", "reviewed_at": "2026-11-23T00:00:00Z"}]
    )

    approved, updated = apply_review_decisions(documents, manifest, decisions)

    assert approved == [documents[0]]
    assert updated[0]["reviewed_by"] == "sophie-24"
    assert updated[0]["review_status"] == "APPROVED"


def test_reviewed_exclusion_never_enters_approved_output():
    documents, manifest = _rows()
    decisions = parse_review_decisions(
        [{"source_id": "faq:1", "review_status": "EXCLUDED", "reason": "outdated", "reviewed_by": "sophie-24"}]
    )

    approved, updated = apply_review_decisions(documents, manifest, decisions)

    assert not approved
    assert updated[0]["allowed_use"] == "NOT_ALLOWED"


def test_unknown_or_inactive_approval_is_rejected():
    documents, manifest = _rows()
    unknown = parse_review_decisions(
        [{"source_id": "faq:404", "review_status": "APPROVED", "reason": "x", "reviewed_by": "sophie-24"}]
    )
    inactive = parse_review_decisions(
        [{"source_id": "faq:2", "review_status": "APPROVED", "reason": "x", "reviewed_by": "sophie-24"}]
    )

    with pytest.raises(NormalizationError, match="unknown source_id"):
        apply_review_decisions(documents, manifest, unknown)
    with pytest.raises(NormalizationError, match="inactive document"):
        apply_review_decisions(documents, manifest, inactive)


def test_duplicate_decision_is_rejected():
    with pytest.raises(NormalizationError, match="duplicate review decision"):
        parse_review_decisions(
            [
                {"source_id": "faq:1", "review_status": "APPROVED", "reason": "x", "reviewed_by": "sophie-24"},
                {"source_id": "faq:1", "review_status": "EXCLUDED", "reason": "y", "reviewed_by": "sophie-24"},
            ]
        )
