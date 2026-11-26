from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.models import DraftAction, EvidenceKind, GenerationStatus
from app.db.models import (
    AiGenerationLog,
    AiGenerationSource,
    AnswerDraft,
    Brand,
    GenerationPurpose,
    Inquiry,
    InquiryCategory,
    InquiryStatus,
)


BASE = "/api/v1/admin/inquiries"
T0 = datetime(2026, 11, 17, 1, 0, tzinfo=timezone.utc)


def _seed(db: Session) -> dict[str, int]:
    brand = Brand(code="brand_a", name="브랜드 A")
    db.add(brand)
    db.flush()

    membership = InquiryCategory(
        brand_id=brand.id,
        code="membership",
        name="멤버십",
        depth=1,
    )
    event = InquiryCategory(
        brand_id=brand.id,
        code="event",
        name="이벤트",
        depth=1,
    )
    db.add_all([membership, event])
    db.flush()

    grade = InquiryCategory(
        brand_id=brand.id,
        parent_id=membership.id,
        code="membership_grade",
        name="등급",
        depth=2,
    )
    db.add(grade)
    db.flush()

    def inquiry(
        title: str,
        status: InquiryStatus,
        category: InquiryCategory | None,
        minutes: int,
    ) -> Inquiry:
        row = Inquiry(
            brand_id=brand.id,
            category_id=category.id if category else None,
            category_path=["문의", category.name] if category else None,
            title=title,
            content=f"{title} 내용",
            customer_name="가상 고객",
            store_name="가상 매장 1",
            receipt_token=f"token-{title}",
            status=status,
            created_at=T0 + timedelta(minutes=minutes),
        )
        db.add(row)
        return row

    drafted = inquiry(
        "등급 문의", InquiryStatus.PENDING_REVIEW, grade, 3
    )
    escalated = inquiry(
        "이벤트 문의", InquiryStatus.PENDING_REVIEW, event, 2
    )
    generating = inquiry(
        "생성 중 문의", InquiryStatus.DRAFT_GENERATING, None, 1
    )
    answered = inquiry(
        "답변 끝난 문의", InquiryStatus.ANSWERED, membership, 0
    )

    db.flush()

    db.add_all([
        AnswerDraft(
            inquiry_id=drafted.id,
            action=DraftAction.DRAFT_FOR_REVIEW,
            ai_draft_text="AI 초안입니다.",
        ),
        AnswerDraft(
            inquiry_id=escalated.id,
            action=DraftAction.ESCALATE,
            escalation_reason="근거 부족",
        ),
    ])

    log = AiGenerationLog(
        purpose=GenerationPurpose.INQUIRY_DRAFT,
        inquiry_id=drafted.id,
        model="test-model",
        prompt_version="v1",
        status=GenerationStatus.COMPLETED,
        action=DraftAction.DRAFT_FOR_REVIEW,
        latency_ms=10,
    )

    log.sources = [
        AiGenerationSource(
            source_id="chunk_1",
            document_id="doc_12",
            title="등급 안내",
            excerpt="6개월 기준",
            kind=EvidenceKind.OFFICIAL,
            cited=True,
        ),
        AiGenerationSource(
            source_id="chunk_2",
            document_id="doc_13",
            title="미인용 문서",
            excerpt="x",
            kind=EvidenceKind.OFFICIAL,
            cited=False,
        ),
        AiGenerationSource(
            source_id="case_1",
            kind=EvidenceKind.VOC_REFERENCE,
            cited=False,
        ),
    ]

    db.add(log)
    db.commit()

    return {
        "drafted": drafted.id,
        "escalated": escalated.id,
        "generating": generating.id,
        "answered": answered.id,
    }


def _pid(internal_id: int) -> str:
    return f"inq_{internal_id:03d}"


# ---------- 목록 ----------

def test_list_matches_spec_and_is_latest_first(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    body = client.get(BASE).json()

    assert body["code"] == "ADMIN_INQUIRY_LIST_SUCCESS"
    assert body["message"] == "문의 목록 조회에 성공했습니다."

    data = body["data"]

    assert {
        k: data[k] for k in ("page", "pageSize", "total")
    } == {
        "page": 1,
        "pageSize": 20,
        "total": 4,
    }

    assert [i["title"] for i in data["items"]] == [
        "등급 문의",
        "이벤트 문의",
        "생성 중 문의",
        "답변 끝난 문의",
    ]

    assert set(data["items"][0]) == {
        "inquiryId", "title", "categoryPath",
        "status", "createdAt",
    }

    assert data["items"][2]["categoryPath"] == []


def test_list_filters(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    pending = client.get(
        BASE, params={"status": "PENDING_REVIEW"}
    ).json()["data"]

    assert pending["total"] == 2

    membership = client.get(
        BASE, params={"category": "MEMBERSHIP"}
    ).json()["data"]

    assert [i["title"] for i in membership["items"]] == [
        "등급 문의", "답변 끝난 문의"
    ]

    both = client.get(
        BASE,
        params={
            "status": "ANSWERED",
            "category": "membership",
        },
    ).json()["data"]

    assert [i["title"] for i in both["items"]] == [
        "답변 끝난 문의"
    ]


def test_list_pagination_and_errors(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    second = client.get(
        BASE, params={"page": 2, "pageSize": 3}
    ).json()["data"]

    assert (
        second["page"],
        second["pageSize"],
        second["total"],
        len(second["items"]),
    ) == (2, 3, 4, 1)

    for params in (
        {"page": 0},
        {"pageSize": 101},
        {"status": "NOPE"},
    ):
        response = client.get(BASE, params=params)

        assert (
            response.status_code,
            response.json()["code"],
        ) == (400, "INVALID_PARAMETER"), params


# ---------- 상세 ----------

def test_detail_with_ai_draft_and_cited_sources(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    body = client.get(
        f"{BASE}/{_pid(ids['drafted'])}"
    ).json()

    assert body["code"] == "ADMIN_INQUIRY_DETAIL_SUCCESS"

    data = body["data"]

    assert set(data) == {
        "inquiryId", "title", "content",
        "customerName", "storeName", "categoryPath",
        "summary", "categorySuggestion", "status",
        "draft", "createdAt", "updatedAt",
    }

    assert data["draft"] == {
        "answerText": "AI 초안입니다.",
        "sources": [
            {
                "documentId": "doc_12",
                "title": "등급 안내",
                "excerpt": "6개월 기준",
            },
        ],
    }

    assert data["summary"] is None


def test_detail_of_escalated_and_generating(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    escalated = client.get(
        f"{BASE}/{_pid(ids['escalated'])}"
    ).json()["data"]

    assert escalated["draft"] == {
        "answerText": None, "sources": []
    }

    generating = client.get(
        f"{BASE}/{_pid(ids['generating'])}"
    ).json()["data"]

    assert generating["draft"] == {
        "answerText": None, "sources": []
    }


def test_detail_errors(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    bad = client.get(f"{BASE}/abc")

    assert (
        bad.status_code,
        bad.json()["code"],
    ) == (400, "INVALID_PARAMETER")

    missing = client.get(f"{BASE}/inq_999")

    assert (
        missing.status_code,
        missing.json()["code"],
    ) == (404, "INQUIRY_NOT_FOUND")


# ---------- 초안 수정 ----------

def test_update_draft_keeps_status_and_overrides_ai_text(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    response = client.put(
        f"{BASE}/{_pid(ids['drafted'])}/draft",
        json={"answerText": "  수정한 답변  "},
    )

    body = response.json()

    assert body["code"] == "ADMIN_DRAFT_UPDATED"
    assert body["message"] == "답변 초안을 저장했습니다."

    assert {
        k: body["data"][k]
        for k in ("status", "answerText")
    } == {
        "status": "PENDING_REVIEW",
        "answerText": "수정한 답변",
    }

    assert "updatedAt" in body["data"]

    detail = client.get(
        f"{BASE}/{_pid(ids['drafted'])}"
    ).json()["data"]

    assert detail["draft"]["answerText"] == "수정한 답변"

    escalated = client.put(
        f"{BASE}/{_pid(ids['escalated'])}/draft",
        json={"answerText": "직접 작성"},
    )

    assert escalated.status_code == 200


def test_update_draft_errors(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    blank = client.put(
        f"{BASE}/{_pid(ids['drafted'])}/draft",
        json={"answerText": "  "},
    )

    assert (
        blank.status_code,
        blank.json()["code"],
    ) == (400, "INVALID_INPUT")

    answered = client.put(
        f"{BASE}/{_pid(ids['answered'])}/draft",
        json={"answerText": "x"},
    )

    assert (
        answered.status_code,
        answered.json()["code"],
    ) == (409, "INQUIRY_ALREADY_ANSWERED")

    generating = client.put(
        f"{BASE}/{_pid(ids['generating'])}/draft",
        json={"answerText": "x"},
    )

    assert (
        generating.status_code,
        generating.json()["code"],
    ) == (409, "INVALID_STATUS_TRANSITION")

    missing = client.put(
        f"{BASE}/inq_999/draft",
        json={"answerText": "x"},
    )

    assert (
        missing.status_code,
        missing.json()["code"],
    ) == (404, "INQUIRY_NOT_FOUND")


# ---------- 답변 승인 ----------

def test_approve_publishes_answer_to_customer(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    body = client.post(
        f"{BASE}/{_pid(ids['drafted'])}/approve",
        json={"approvedAnswer": "최종 답변"},
    ).json()

    assert body["code"] == "ADMIN_ANSWER_APPROVED"
    assert body["message"] == "답변을 등록했습니다."
    assert body["data"]["status"] == "ANSWERED"
    assert body["data"]["answeredAt"] is not None

    customer = client.get(
        f"/api/v1/inquiries/{_pid(ids['drafted'])}",
        params={"receiptToken": "token-등급 문의"},
    ).json()["data"]

    assert customer["finalAnswer"] == "최종 답변"


def test_approve_errors(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    blank = client.post(
        f"{BASE}/{_pid(ids['drafted'])}/approve",
        json={"approvedAnswer": ""},
    )

    assert (
        blank.status_code,
        blank.json()["code"],
    ) == (400, "INVALID_INPUT")

    for key in ("answered", "generating"):
        response = client.post(
            f"{BASE}/{_pid(ids[key])}/approve",
            json={"approvedAnswer": "x"},
        )

        assert (
            response.status_code,
            response.json()["code"],
        ) == (409, "INVALID_STATUS_TRANSITION"), key


# ---------- 상태 변경 ----------

def test_change_status_with_memo(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    body = client.patch(
        f"{BASE}/{_pid(ids['drafted'])}/status",
        json={
            "status": "IN_REVIEW",
            "memo": "할인 정책 담당자 확인 중입니다.",
        },
    ).json()

    assert body["code"] == "UPDATE_INQUIRY_STATUS_SUCCESS"
    assert body["message"] == "문의 상태 변경에 성공했습니다."

    assert {
        k: body["data"][k]
        for k in ("previousStatus", "status")
    } == {
        "previousStatus": "PENDING_REVIEW",
        "status": "IN_REVIEW",
    }

    db_session.expire_all()

    assert db_session.get(
        Inquiry, ids["drafted"]
    ).admin_memo == "할인 정책 담당자 확인 중입니다."


@pytest.mark.parametrize(
    "key, target, expected",
    [
        ("drafted", "CLOSED", 200),
        ("answered", "CLOSED", 200),
        ("drafted", "ANSWERED", 409),
        ("drafted", "PENDING_REVIEW", 409),
        ("generating", "PENDING_REVIEW", 409),
        ("answered", "IN_REVIEW", 409),
    ],
)
def test_status_transitions(
    client: TestClient,
    db_session: Session,
    key: str,
    target: str,
    expected: int,
) -> None:
    ids = _seed(db_session)

    response = client.patch(
        f"{BASE}/{_pid(ids[key])}/status",
        json={"status": target},
    )

    assert response.status_code == expected

    if expected == 409:
        assert response.json()["code"] == (
            "INVALID_STATUS_TRANSITION"
        )


def test_change_status_errors(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    invalid = client.patch(
        f"{BASE}/{_pid(ids['drafted'])}/status",
        json={"status": "AI_DRAFTED"},
    )

    assert (
        invalid.status_code,
        invalid.json()["code"],
    ) == (400, "INVALID_STATUS")

    missing = client.patch(
        f"{BASE}/inq_999/status",
        json={"status": "CLOSED"},
    )

    assert (
        missing.status_code,
        missing.json()["code"],
    ) == (404, "INQUIRY_NOT_FOUND")