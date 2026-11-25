from app.rag.pipeline.voc import prepare_voc_case, prepare_voc_rows


def test_voc_uses_allow_list_and_never_emits_identity_or_internal_fields():
    case = prepare_voc_case(
        {
            "id": 10,
            "title": "쿠폰 문의",
            "content": "쿠폰 적용이 어렵습니다.",
            "answer": "적용 조건을 안내했습니다.",
            "categoryPath": "문의 > 쿠폰",
            "writerName": "홍길동",
            "email": "person@example.com",
            "phoneNumber": "010-1234-5678",
            "mbId": "member-1",
            "orderInfo": "private order",
            "memo": "internal note",
            "fileInfos": [{"name": "attachment"}],
        },
        source_name="web-voc",
    )

    row = case.as_quarantine_row()
    assert case.case_status == "READY_FOR_REVIEW"
    assert row["usage_scope"] == "AGENT_REFERENCE_ONLY"
    assert row["allowed_use"] == "AGENT_REFERENCE_ONLY"
    assert row["document_version"] == "voc-quarantined-v1"
    assert "홍길동" not in str(row)
    assert "person@example.com" not in str(row)
    assert "internal note" not in str(row)


def test_voc_masks_contact_identifiers_written_inside_customer_text():
    case = prepare_voc_case(
        {
            "id": 15,
            "title": "연락 요청 010-9876-5432",
            "content": "답변은 help@example.com 또는 010 9876 5432로 부탁드립니다.",
            "answer": "help@example.com으로 회신했습니다.",
        },
        source_name="web-voc",
    )

    row = case.as_quarantine_row()
    assert "010-9876-5432" not in str(row)
    assert "help@example.com" not in str(row)
    assert "[REDACTED_PHONE]" in str(row)
    assert "[REDACTED_EMAIL]" in str(row)


def test_order_and_safety_cases_are_excluded_from_voc_reference_artifacts():
    order = prepare_voc_case(
        {"id": 11, "title": "주문 문의", "content": "주문번호: ABCD1234", "answer": "확인"},
        source_name="web-voc",
    )
    safety = prepare_voc_case(
        {"id": 12, "title": "이물질", "content": "음식에서 이물질 발견", "answer": "담당자가 확인"},
        source_name="call-voc",
    )

    assert order.case_status == "EXCLUDED"
    assert order.exclusion_reason == "individual order or account context"
    assert safety.case_status == "EXCLUDED"
    assert safety.exclusion_reason == "safety or legal risk"
    assert "text" not in order.as_quarantine_row()


def test_voc_without_resolution_is_excluded_and_invalid_rows_are_rejected():
    cases, rejected = prepare_voc_rows(
        [
            {"id": 13, "title": "미완료", "content": "문의만 있음", "answer": ""},
            {"id": 14, "content": "제목 누락", "answer": "처리"},
        ],
        source_name="web-voc",
    )

    assert cases[0].case_status == "EXCLUDED"
    assert cases[0].exclusion_reason == "missing resolution"
    assert rejected == [{"line": 2, "reason": "missing required VOC title"}]
