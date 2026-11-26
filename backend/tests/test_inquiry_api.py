from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import (
    DraftAction,
    DraftResult,
    GenerationEvent,
    GenerationStatus,
)
from app.ai.service import InquiryAiService
from app.api.inquiries import get_draft_scheduler
from app.db.models import (
    AnswerDraft,
    Brand,
    Inquiry,
    InquiryCategory,
    InquiryStatus,
    InquiryType,
)
from app.main import app
from app.services import inquiry_service


@pytest.fixture
def scheduled(client: TestClient) -> Iterator[list[int]]:
    """실제 AI 실행 대신 문의 ID만 기록한다."""
    calls: list[int] = []
    app.dependency_overrides[get_draft_scheduler] = (
        lambda: calls.append
    )

    try:
        yield calls
    finally:
        app.dependency_overrides.pop(
            get_draft_scheduler, None
        )


def _seed(db: Session) -> None:
    brand = Brand(code="brand_a", name="브랜드 A")
    db.add(brand)
    db.flush()

    event = InquiryCategory(
        brand_id=brand.id,
        code="event",
        name="이벤트",
        depth=1,
    )
    db.add(event)
    db.flush()

    discount = InquiryCategory(
        brand_id=brand.id,
        parent_id=event.id,
        code="event_discount",
        name="할인 혜택",
        depth=2,
    )
    db.add(discount)
    db.flush()

    db.add(
        InquiryCategory(
            brand_id=brand.id,
            parent_id=discount.id,
            code="event_discount_partner",
            name="제휴 할인",
            depth=3,
        )
    )
    db.commit()


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "brandId": "brand_a",
        "categoryPath": ["문의", "제휴 할인", "적용 방법"],
        "title": "제휴 할인이 적용되지 않아요",
        "content": "결제 단계에서 제휴 할인이 보이지 않습니다.",
        "customerName": "가상 고객",
        "storeName": "가상 매장 1",
        "privacyConsent": True,
    }

    body.update(overrides)
    return body


# ---------- 문의 등록 ----------

def test_create_inquiry_returns_202_and_schedules_ai(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    response = client.post(
        "/api/v1/inquiries", json=_body()
    )

    assert response.status_code == 202

    body = response.json()

    assert body["status"] == 202
    assert body["code"] == "INQUIRY_CREATED"
    assert body["message"] == "문의가 접수되었습니다."

    data = body["data"]

    assert set(data) == {
        "inquiryId",
        "receiptToken",
        "status",
        "createdAt",
    }
    assert data["status"] == "DRAFT_GENERATING"
    assert data["inquiryId"].startswith("inq_")

    inquiry = db_session.scalar(select(Inquiry))

    assert scheduled == [inquiry.id]
    assert data["receiptToken"] == inquiry.receipt_token
    assert inquiry.privacy_consented_at is not None


def test_category_path_resolves_type_and_deepest_category(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    client.post("/api/v1/inquiries", json=_body())

    inquiry = db_session.scalar(select(Inquiry))

    assert inquiry.category_path == [
        "문의", "제휴 할인", "적용 방법"
    ]
    assert inquiry.inquiry_type is InquiryType.QUESTION
    assert inquiry.category.code == "event_discount_partner"


def test_category_path_type_detection_and_unknown_names(
    db_session: Session,
) -> None:
    _seed(db_session)

    brand_id = db_session.scalar(select(Brand.id))

    inquiry_type, category = inquiry_service.classify(
        db_session,
        brand_id=brand_id,
        category_path=["불만", "이벤트"],
    )

    assert inquiry_type is InquiryType.COMPLAINT
    assert category.code == "event"

    inquiry_type, category = inquiry_service.classify(
        db_session,
        brand_id=brand_id,
        category_path=["모르는 분류"],
    )

    assert inquiry_type is InquiryType.QUESTION
    assert category is None

    assert inquiry_service.classify(
        db_session,
        brand_id=brand_id,
        category_path=None,
    ) == (InquiryType.QUESTION, None)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"title": None}, "INVALID_INPUT"),
        ({"title": "   "}, "INVALID_INPUT"),
        ({"content": ""}, "INVALID_INPUT"),
        ({"privacyConsent": False}, "INVALID_INPUT"),
    ],
)
def test_invalid_input(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
    overrides: dict,
    code: str,
) -> None:
    _seed(db_session)

    response = client.post(
        "/api/v1/inquiries",
        json=_body(**overrides),
    )

    assert response.status_code == 400
    assert response.json()["code"] == code
    assert scheduled == []


@pytest.mark.parametrize(
    "missing",
    [
        "brandId",
        "title",
        "content",
        "customerName",
        "privacyConsent",
    ],
)
def test_missing_parameter(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
    missing: str,
) -> None:
    _seed(db_session)

    body = _body()
    body.pop(missing)

    response = client.post(
        "/api/v1/inquiries", json=body
    )

    assert response.status_code == 400
    assert response.json()["code"] == "MISSING_PARAMETER"


def test_unknown_brand(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    response = client.post(
        "/api/v1/inquiries",
        json=_body(brandId="nope"),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "BRAND_NOT_FOUND"
    assert scheduled == []


# ---------- 고객 조회 ----------

def _create(client: TestClient) -> dict[str, str]:
    return client.post(
        "/api/v1/inquiries", json=_body()
    ).json()["data"]


def test_status_lookup_before_answer_hides_drafts(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    created = _create(client)
    inquiry = db_session.scalar(select(Inquiry))

    db_session.add(
        AnswerDraft(
            inquiry_id=inquiry.id,
            action=DraftAction.DRAFT_FOR_REVIEW,
            ai_draft_text="AI 초안",
        )
    )

    inquiry.status = InquiryStatus.PENDING_REVIEW
    db_session.commit()

    body = client.get(
        f"/api/v1/inquiries/{created['inquiryId']}",
        params={
            "receiptToken": created["receiptToken"]
        },
    ).json()

    assert body["code"] == "GET_INQUIRY_STATUS_SUCCESS"
    assert body["message"] == "문의 처리 상태 조회에 성공했습니다."

    data = body["data"]

    assert set(data) == {
        "inquiryId",
        "title",
        "inquiryType",
        "status",
        "statusLabel",
        "createdAt",
        "answeredAt",
        "finalAnswer",
    }

    assert data["status"] == "PENDING_REVIEW"
    assert data["statusLabel"] == "답변 준비 중"
    assert data["finalAnswer"] is None
    assert data["answeredAt"] is None


def test_status_lookup_after_answer(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    created = _create(client)
    inquiry = db_session.scalar(select(Inquiry))

    inquiry.status = InquiryStatus.ANSWERED
    inquiry.answer_content = (
        "확인 결과, 다른 할인과 중복 적용되지 않습니다."
    )
    inquiry.answered_at = datetime(
        2026, 11, 17, 5, 5,
        tzinfo=timezone.utc,
    )

    db_session.commit()

    data = client.get(
        f"/api/v1/inquiries/{created['inquiryId']}",
        params={
            "receiptToken": created["receiptToken"]
        },
    ).json()["data"]

    assert data["statusLabel"] == "답변 완료"
    assert data["inquiryType"] == "QUESTION"
    assert data["finalAnswer"] == (
        "확인 결과, 다른 할인과 중복 적용되지 않습니다."
    )
    assert data["answeredAt"] is not None


def test_status_lookup_errors(
    client: TestClient,
    db_session: Session,
    scheduled: list[int],
) -> None:
    _seed(db_session)

    created = _create(client)
    path = f"/api/v1/inquiries/{created['inquiryId']}"

    missing = client.get(path)

    assert (
        missing.status_code,
        missing.json()["code"],
    ) == (400, "MISSING_RECEIPT_TOKEN")

    for token in (
        "00000000-0000-0000-0000-000000000000",
        "잘못된토큰",
    ):
        wrong = client.get(
            path,
            params={"receiptToken": token},
        )

        assert (
            wrong.status_code,
            wrong.json()["code"],
        ) == (403, "INVALID_RECEIPT_TOKEN")

    for unknown in ("inq_999", "faq_001", "abc"):
        response = client.get(
            f"/api/v1/inquiries/{unknown}",
            params={
                "receiptToken": created["receiptToken"]
            },
        )

        assert (
            response.status_code,
            response.json()["code"],
        ) == (404, "INQUIRY_NOT_FOUND"), unknown


# ---------- AI 초안 백그라운드 실행 ----------

class _FakeGraph:
    def invoke(
        self, _: dict[str, object]
    ) -> dict[str, object]:
        return {
            "result": DraftResult(
                action=DraftAction.DRAFT_FOR_REVIEW,
                draft_text="검토용 초안",
                escalation_reason=None,
                cited_source_ids=["doc_1"],
                event=GenerationEvent(
                    "test-model",
                    "v1",
                    ["doc_1"],
                    [],
                    10,
                    GenerationStatus.COMPLETED,
                ),
            )
        }


def _stored_inquiry(db: Session) -> int:
    _seed(db)

    brand_id = db.scalar(select(Brand.id))

    inquiry = inquiry_service.create_inquiry(
        db,
        inquiry_service.NewInquiry(
            brand_id,
            None,
            "제목",
            "내용",
            "가상 고객",
            None,
        ),
    )

    return inquiry.id


def test_run_ai_draft_saves_result(
    db_session: Session,
) -> None:
    inquiry_id = _stored_inquiry(db_session)

    inquiry_service.run_ai_draft(
        inquiry_id,
        session_factory=(
            inquiry_service.session_factory_for(db_session)
        ),
        service_factory=lambda session: InquiryAiService(
            session, _FakeGraph()
        ),
    )

    db_session.expire_all()
    inquiry = db_session.get(Inquiry, inquiry_id)

    assert inquiry.status is InquiryStatus.PENDING_REVIEW
    assert inquiry.draft.ai_draft_text == "검토용 초안"


def test_run_ai_draft_failure_falls_back_to_manual_review(
    db_session: Session,
) -> None:
    inquiry_id = _stored_inquiry(db_session)

    def broken(_: Session) -> object:
        raise RuntimeError("Chroma is down")

    inquiry_service.run_ai_draft(
        inquiry_id,
        session_factory=(
            inquiry_service.session_factory_for(db_session)
        ),
        service_factory=broken,
    )

    db_session.expire_all()
    inquiry = db_session.get(Inquiry, inquiry_id)

    assert inquiry.status is InquiryStatus.PENDING_REVIEW
    assert inquiry.draft.ai_draft_text is None
    assert inquiry.draft.escalation_reason == (
        inquiry_service.AI_FAILURE_REASON
    )


def test_ai_input_masks_contact_details(
    db_session: Session,
) -> None:
    _seed(db_session)

    brand_id = db_session.scalar(select(Brand.id))

    inquiry = inquiry_service.create_inquiry(
        db_session,
        inquiry_service.NewInquiry(
            brand_id,
            None,
            "연락 부탁",
            "010-1234-5678 / test@example.com 으로 연락주세요",
            "가상 고객",
            None,
        ),
    )

    seen: list[str] = []

    class _Recorder(_FakeGraph):
        def invoke(
            self, state: dict[str, object]
        ) -> dict[str, object]:
            seen.append(str(state["inquiry_text"]))
            return super().invoke(state)

    inquiry_service.run_ai_draft(
        inquiry.id,
        session_factory=(
            inquiry_service.session_factory_for(db_session)
        ),
        service_factory=lambda session: InquiryAiService(
            session, _Recorder()
        ),
    )

    assert "010-1234-5678" not in seen[0]
    assert "test@example.com" not in seen[0]