from app.rag.pipeline.normalization import (
    NormalizationError,
    normalize_faq_record,
    normalize_rows,
    normalize_voc_record,
)


def test_faq_normalization_masks_pii_and_matches_ingestion_contract():
    result = normalize_faq_record(
        {
            "faq_id": "12",
            "question": "<b>배송 문의</b>",
            "answer": "test@example.com 또는 010-1234-5678로 연락하세요.",
            "category": " 배송 ",
            "updated_at": "2026-11-22",
        }
    )

    assert result.as_ingestion_row() == {
        "source_id": "faq:12",
        "title": "FAQ: 배송 문의",
        "text": "질문: 배송 문의\n답변: [EMAIL_REDACTED] 또는 [PHONE_REDACTED]로 연락하세요.",
        "document_version": "2026-11-22",
        "source_type": "official",
        "category": "배송",
    }


def test_voc_normalization_is_agent_reference_only_source_type():
    result = normalize_voc_record(
        {
            "case_id": "C-1",
            "inquiry": "상품이 누락됐습니다.",
            "resolution": "재배송 접수 완료",
            "category": "배송",
        }
    )

    assert result.source_id == "voc:C-1"
    assert result.source_type == "voc"
    assert result.text == "고객 문의: 상품이 누락됐습니다.\n처리 결과: 재배송 접수 완료"


def test_rejects_missing_and_duplicate_rows_without_including_raw_content():
    accepted, rejected = normalize_rows(
        [
            {"faq_id": "1", "question": "Q", "answer": "A"},
            {"faq_id": "1", "question": "Q2", "answer": "A2"},
            {"faq_id": "3", "question": "Q3"},
        ],
        "faq",
    )

    assert len(accepted) == 1
    assert rejected == [
        {"line": 2, "reason": "duplicate source id"},
        {"line": 3, "reason": "missing required FAQ answer"},
    ]


def test_normalization_error_for_missing_required_voc_inquiry():
    try:
        normalize_voc_record({"case_id": "C-1"})
    except NormalizationError as error:
        assert str(error) == "missing required VOC inquiry"
    else:
        raise AssertionError("NormalizationError was not raised")
