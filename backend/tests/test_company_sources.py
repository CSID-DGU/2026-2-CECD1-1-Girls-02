from app.rag.pipeline.company_sources import (
    draft_eligible,
    policy_profile,
    prepare_company_faq_rows,
    prepare_markdown_sections,
)


def test_active_company_faq_is_prepared_but_requires_review_before_drafting():
    documents, rejected = prepare_company_faq_rows(
        [
            {
                "id": "faq-1",
                "categoryName": "쿠폰 및 상품권",
                "title": "쿠폰 사용 방법",
                "content": "결제 단계에서 쿠폰을 선택합니다.",
                "active": True,
                "modifiedTime": "2026-11-22T10:00:00",
                "contentAttachments": [{"name": "ignored.pdf"}],
            }
        ]
    )

    document = documents[0]
    assert not rejected
    assert document.category_code == "COUPON"
    assert document.review_status == "PENDING_REVIEW"
    assert document.allowed_use == "DRAFT_ONLY"
    assert "ignored.pdf" not in document.text
    assert not draft_eligible(document)


def test_inactive_faq_is_preserved_as_excluded_and_cannot_support_drafts():
    documents, _ = prepare_company_faq_rows(
        [{"id": "faq-2", "title": "종료 FAQ", "content": "종료", "active": False}]
    )

    document = documents[0]
    assert document.raw_status == "INACTIVE"
    assert document.review_status == "EXCLUDED"
    assert document.allowed_use == "NOT_ALLOWED"
    assert not draft_eligible(document)


def test_missing_required_faq_data_is_rejected_without_raw_text_in_audit():
    documents, rejected = prepare_company_faq_rows(
        [{"id": "faq-3", "title": "누락 답변", "active": True}]
    )

    assert not documents
    assert rejected == [{"line": 1, "reason": "missing required FAQ content"}]


def test_policy_sections_are_pending_review_and_franchise_is_handoff_only():
    markdown = "# 제목\n\n## 혜택\n\n쿠폰 규칙\n\n## 예외\n\n중복 적용 불가"
    policy_documents = prepare_markdown_sections(
        markdown,
        source_name="coupon",
        profile=policy_profile("policy", "COUPON"),
        document_version="2025-04-22",
    )
    franchise_documents = prepare_markdown_sections(
        markdown,
        source_name="franchise",
        profile=policy_profile("franchise", "FRANCHISE"),
    )

    assert len(policy_documents) == 2
    assert all(item.review_status == "PENDING_REVIEW" for item in policy_documents)
    assert all(not draft_eligible(item) for item in policy_documents)
    assert all(item.allowed_use == "HANDOFF_CONTEXT_ONLY" for item in franchise_documents)
