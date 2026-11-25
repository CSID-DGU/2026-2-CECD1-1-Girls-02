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


def test_company_faq_replaces_masked_070_support_number_with_public_placeholder():
    documents, _ = prepare_company_faq_rows(
        [{"id": "faq-phone", "title": "변경 문의", "content": "070-****-1991로 전화", "active": True}]
    )

    assert "070-0000-0000" in documents[0].text
    assert "070-****-1991" not in documents[0].text


def test_company_faq_removes_brand_alias_from_indexable_text():
    documents, _ = prepare_company_faq_rows(
        [{"id": "faq-brand", "title": "pizzaalvolo 안내", "content": "피자알볼로 사이트", "active": True}]
    )

    assert "alvolo" not in documents[0].text.lower()
    assert "pizza 안내" in documents[0].text


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


def test_policy_and_franchise_sections_are_pending_review_before_drafting():
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
    assert all(item.allowed_use == "DRAFT_ONLY" for item in franchise_documents)


def test_level_one_content_section_is_not_lost_when_followed_by_level_two_sections():
    markdown = "# 문서 제목\n\n# 1. 스탬프\n\n스탬프는 결제 후 지급됩니다.\n\n## 2. 등급\n\n등급 혜택 안내"

    documents = prepare_markdown_sections(
        markdown,
        source_name="membership",
        profile=policy_profile("policy", "MEMBERSHIP"),
    )

    assert [document.title for document in documents] == [
        "membership - 1. 스탬프",
        "membership - 2. 등급",
    ]
    assert "스탬프는 결제 후 지급됩니다." in documents[0].text


def test_user_faq_profile_is_official_faq_and_requires_review():
    profile = policy_profile("faq-guide", "GENERAL")

    assert profile.doc_type == "FAQ"
    assert profile.authority_level == "OFFICIAL_FAQ"
    assert profile.allowed_use == "DRAFT_ONLY"
