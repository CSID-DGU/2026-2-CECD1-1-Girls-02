from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.models import (
    DraftAction,
    EvidenceKind,
    GenerationStatus,
)
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


PERIOD = {
    "from": "2026-11-17",
    "to": "2026-11-17",
}


def _utc(
    day: int,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026, 11, day, hour, minute,
        tzinfo=timezone.utc,
    )


def _seed(db: Session) -> None:
    brand = Brand(
        code="brand_a",
        name="브랜드 A",
    )

    db.add(brand)
    db.flush()

    discount = InquiryCategory(
        brand_id=brand.id,
        code="event_discount",
        name="할인 혜택",
        depth=1,
    )

    grade = InquiryCategory(
        brand_id=brand.id,
        code="membership_grade",
        name="등급",
        depth=1,
    )

    db.add_all([discount, grade])
    db.flush()

    def inquiry(
        n: int,
        status: InquiryStatus,
        category: InquiryCategory | None,
        created: datetime,
        action: DraftAction | None = None,
    ) -> Inquiry:
        row = Inquiry(
            brand_id=brand.id,
            category_id=category.id if category else None,
            title=f"문의 {n}",
            content="내용",
            customer_name="가상 고객",
            receipt_token=f"t{n}",
            status=status,
            created_at=created,
        )

        db.add(row)
        db.flush()

        if action is not None:
            db.add(
                AnswerDraft(
                    inquiry_id=row.id,
                    action=action,
                )
            )

        return row

    # KST 11월 17일 범위에 포함되는 문의
    inquiry(
        1, InquiryStatus.DRAFT_GENERATING,
        discount, _utc(16, 15, 30),
    )
    inquiry(
        2, InquiryStatus.PENDING_REVIEW,
        discount, _utc(17, 1),
        DraftAction.DRAFT_FOR_REVIEW,
    )
    inquiry(
        3, InquiryStatus.PENDING_REVIEW,
        grade, _utc(17, 2),
        DraftAction.ESCALATE,
    )
    inquiry(
        4, InquiryStatus.IN_REVIEW,
        discount, _utc(17, 3),
        DraftAction.DRAFT_FOR_REVIEW,
    )
    inquiry(
        5, InquiryStatus.ANSWERED,
        None, _utc(17, 4),
    )
    inquiry(
        6, InquiryStatus.CLOSED,
        grade, _utc(17, 14, 59),
    )

    # KST 11월 17일 범위 밖의 문의
    inquiry(
        7, InquiryStatus.ANSWERED,
        discount, _utc(16, 14, 30),
    )
    inquiry(
        8, InquiryStatus.ANSWERED,
        discount, _utc(17, 15, 0),
    )

    def log(
        purpose: GenerationPurpose,
        status: GenerationStatus,
        action: DraftAction,
        latency: int,
        created: datetime,
        cited: bool = False,
        tokens: tuple[int, int] | None = None,
    ) -> None:
        row = AiGenerationLog(
            purpose=purpose,
            model="m",
            prompt_version="v1",
            status=status,
            action=action,
            latency_ms=latency,
            created_at=created,
            input_tokens=tokens[0] if tokens else None,
            output_tokens=tokens[1] if tokens else None,
        )

        row.sources = [
            AiGenerationSource(
                source_id="c1",
                kind=EvidenceKind.OFFICIAL,
                cited=cited,
            )
        ]

        db.add(row)

    draft = GenerationPurpose.INQUIRY_DRAFT
    chat = GenerationPurpose.CHAT_ANSWER

    ok = GenerationStatus.COMPLETED
    rule = GenerationStatus.RULE_ESCALATED
    err = GenerationStatus.MODEL_ERROR

    answer = DraftAction.DRAFT_FOR_REVIEW
    handoff = DraftAction.ESCALATE

    log(
        draft, ok, answer, 1000,
        _utc(17, 1),
        cited=True,
        tokens=(700, 100),
    )
    log(
        draft, ok, answer, 3000,
        _utc(17, 3),
        cited=False,
        tokens=(740, 170),
    )
    log(
        draft, rule, handoff, 0,
        _utc(17, 2),
    )
    log(
        chat, ok, answer, 2000,
        _utc(17, 5),
        cited=True,
        tokens=(500, 80),
    )
    log(
        chat, err, handoff, 20000,
        _utc(17, 6),
    )

    # 기간 밖의 AI 실행 기록
    log(
        draft, ok, answer, 9999,
        _utc(18, 1),
        cited=True,
    )

    db.commit()


# ---------- 대시보드 ----------

def test_dashboard_summary_matches_spec(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed(db_session)

    body = client.get(
        "/api/v1/admin/dashboard/summary",
        params=PERIOD,
    ).json()

    assert body["code"] == "GET_ADMIN_DASHBOARD_SUCCESS"
    assert body["message"] == (
        "관리자 대시보드 요약 조회에 성공했습니다."
    )

    data = body["data"]

    assert data["period"] == {
        "from": "2026-11-17",
        "to": "2026-11-17",
    }

    assert data["inquiryCounts"] == {
        "total": 6,
        "received": 1,
        "aiDrafted": 2,
        "inReview": 1,
        "answered": 1,
        "closed": 1,
    }

    assert data["topCategories"] == [
        {
            "categoryId": "event_discount",
            "categoryName": "할인 혜택",
            "count": 3,
        },
        {
            "categoryId": "membership_grade",
            "categoryName": "등급",
            "count": 2,
        },
    ]

    assert data["aiSummary"] == {
        "draftGeneratedCount": 2,
        "handoffCount": 1,
        "averageLatencyMs": 1333,
    }


def test_dashboard_empty_period(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed(db_session)

    data = client.get(
        "/api/v1/admin/dashboard/summary",
        params={
            "from": "2026-01-01",
            "to": "2026-01-02",
        },
    ).json()["data"]

    assert data["inquiryCounts"]["total"] == 0
    assert data["topCategories"] == []

    assert data["aiSummary"] == {
        "draftGeneratedCount": 0,
        "handoffCount": 0,
        "averageLatencyMs": None,
    }


def test_default_period_is_last_30_days(
    client: TestClient,
    db_session: Session,
) -> None:
    period = client.get(
        "/api/v1/admin/dashboard/summary"
    ).json()["data"]["period"]

    start = datetime.fromisoformat(period["from"])
    end = datetime.fromisoformat(period["to"])

    assert (end - start).days == 29


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/dashboard/summary",
        "/api/v1/admin/metrics/ai",
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        {
            "from": "2026-11-18",
            "to": "2026-11-17",
        },
        {
            "from": "not-a-date",
        },
    ],
)
def test_invalid_period(
    client: TestClient,
    path: str,
    params: dict[str, str],
) -> None:
    response = client.get(
        path,
        params=params,
    )

    assert (
        response.status_code,
        response.json()["code"],
    ) == (400, "INVALID_PARAMETER")


# ---------- AI 처리 성능 ----------

def test_ai_metrics_all_purposes(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed(db_session)

    body = client.get(
        "/api/v1/admin/metrics/ai",
        params=PERIOD,
    ).json()

    assert body["code"] == "GET_AI_METRICS_SUCCESS"
    assert body["message"] == (
        "AI 처리 성능 조회에 성공했습니다."
    )

    data = body["data"]

    assert data == {
        "period": {
            "from": "2026-11-17",
            "to": "2026-11-17",
        },
        "purpose": None,
        "totalRuns": 5,
        "successRate": 0.8,
        "averageLatencyMs": 5200,
        "p95LatencyMs": 20000,
        "averageInputTokens": 647,
        "averageOutputTokens": 117,
        "averageTokensPerSecond": 65.6,
        "answerRate": 0.6,
        "handoffRate": 0.4,
        "sourceAttachedRate": 0.6667,
    }


def test_ai_metrics_by_purpose(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed(db_session)

    data = client.get(
        "/api/v1/admin/metrics/ai",
        params={
            **PERIOD,
            "purpose": "CHAT_ANSWER",
        },
    ).json()["data"]

    assert data["purpose"] == "CHAT_ANSWER"

    assert (
        data["totalRuns"],
        data["successRate"],
        data["handoffRate"],
    ) == (2, 0.5, 0.5)

    bad = client.get(
        "/api/v1/admin/metrics/ai",
        params={"purpose": "NOPE"},
    )

    assert (
        bad.status_code,
        bad.json()["code"],
    ) == (400, "INVALID_PARAMETER")


def test_ai_metrics_without_runs(
    client: TestClient,
    db_session: Session,
) -> None:
    data = client.get(
        "/api/v1/admin/metrics/ai",
        params=PERIOD,
    ).json()["data"]

    assert data["totalRuns"] == 0

    assert all(
        data[key] is None
        for key in (
            "successRate",
            "averageLatencyMs",
            "p95LatencyMs",
            "answerRate",
        )
    )