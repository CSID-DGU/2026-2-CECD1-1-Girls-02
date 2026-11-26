"""관리자 문의 처리: 목록·상세·초안 수정·답변 승인·상태 변경."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.models import EvidenceKind
from app.core.errors import AppError, ErrorCode
from app.db.models import (
    AiGenerationLog,
    AiGenerationSource,
    AnswerDraft,
    GenerationPurpose,
    Inquiry,
    InquiryCategory,
    InquiryStatus,
)


ALLOWED_TRANSITIONS: dict[InquiryStatus, set[InquiryStatus]] = {
    InquiryStatus.PENDING_REVIEW: {
        InquiryStatus.IN_REVIEW,
        InquiryStatus.CLOSED,
    },
    InquiryStatus.IN_REVIEW: {
        InquiryStatus.PENDING_REVIEW,
        InquiryStatus.CLOSED,
    },
    InquiryStatus.ANSWERED: {
        InquiryStatus.CLOSED,
    },
}

REVIEWABLE = {
    InquiryStatus.PENDING_REVIEW,
    InquiryStatus.IN_REVIEW,
}

FINISHED = {
    InquiryStatus.ANSWERED,
    InquiryStatus.CLOSED,
}


# ---------- 조회 ----------

def _category_ids_matching(
    db: Session, code: str
) -> set[int]:
    """일치하는 카테고리와 하위 분류 ID 전체를 반환한다."""

    categories = db.scalars(
        select(InquiryCategory)
    ).all()

    children: dict[int | None, list[InquiryCategory]] = {}

    for category in categories:
        children.setdefault(
            category.parent_id, []
        ).append(category)

    result: set[int] = set()

    stack = [
        c for c in categories
        if c.code.lower() == code.lower()
    ]

    while stack:
        category = stack.pop()

        if category.id not in result:
            result.add(category.id)
            stack.extend(
                children.get(category.id, [])
            )

    return result


def list_inquiries(
    db: Session,
    *,
    status: InquiryStatus | None,
    category: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Inquiry], int]:
    """최신 등록순으로 조회한다. page는 1부터 시작한다."""

    stmt = select(Inquiry)

    if status is not None:
        stmt = stmt.where(Inquiry.status == status)

    if category and category.strip():
        stmt = stmt.where(
            Inquiry.category_id.in_(
                _category_ids_matching(db, category.strip())
            )
        )

    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0

    rows = db.scalars(
        stmt.order_by(
            Inquiry.created_at.desc(),
            Inquiry.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return list(rows), total


def get_inquiry(
    db: Session,
    inquiry_id: int,
    *,
    for_update: bool = False,
) -> Inquiry:
    inquiry = db.get(
        Inquiry,
        inquiry_id,
        with_for_update=for_update,
    )

    if inquiry is None:
        raise AppError(ErrorCode.INQUIRY_NOT_FOUND)

    return inquiry


def draft_sources(
    db: Session,
    inquiry_id: int,
) -> list[AiGenerationSource]:
    """최근 AI 초안에서 실제 인용한 공식 근거만 반환한다."""

    latest = db.scalar(
        select(AiGenerationLog)
        .options(
            selectinload(AiGenerationLog.sources)
        )
        .where(
            AiGenerationLog.inquiry_id == inquiry_id,
            AiGenerationLog.purpose
            == GenerationPurpose.INQUIRY_DRAFT,
        )
        .order_by(
            AiGenerationLog.created_at.desc(),
            AiGenerationLog.id.desc(),
        )
        .limit(1)
    )

    if latest is None:
        return []

    return [
        s for s in latest.sources
        if s.cited and s.kind is EvidenceKind.OFFICIAL
    ]


def answer_text_of(inquiry: Inquiry) -> str | None:
    draft = inquiry.draft

    if draft is None:
        return None

    return (
        draft.edited_text
        if draft.edited_text is not None
        else draft.ai_draft_text
    )


# ---------- 변경 ----------

def save_draft(
    db: Session,
    inquiry_id: int,
    answer_text: str,
) -> tuple[Inquiry, AnswerDraft]:
    inquiry = get_inquiry(
        db, inquiry_id, for_update=True
    )

    if inquiry.status in FINISHED:
        raise AppError(
            ErrorCode.INQUIRY_ALREADY_ANSWERED
        )

    if inquiry.status not in REVIEWABLE:
        raise AppError(
            ErrorCode.INVALID_STATUS_TRANSITION,
            "AI 초안 생성이 끝난 뒤 수정할 수 있습니다.",
        )

    draft = inquiry.draft

    if draft is None:
        draft = AnswerDraft(inquiry_id=inquiry.id)
        db.add(draft)

    draft.edited_text = answer_text

    db.commit()
    db.refresh(draft)

    return inquiry, draft


def approve_answer(
    db: Session,
    inquiry_id: int,
    approved_answer: str,
) -> Inquiry:
    """최종 답변과 상태를 하나의 트랜잭션으로 저장한다."""

    inquiry = get_inquiry(
        db, inquiry_id, for_update=True
    )

    if inquiry.status not in REVIEWABLE:
        raise AppError(
            ErrorCode.INVALID_STATUS_TRANSITION,
            "현재 상태에서는 답변을 승인할 수 없습니다.",
        )

    inquiry.answer_content = approved_answer
    inquiry.answered_at = datetime.now(timezone.utc)
    inquiry.status = InquiryStatus.ANSWERED

    db.commit()
    db.refresh(inquiry)

    return inquiry


@dataclass(frozen=True)
class StatusChange:
    inquiry: Inquiry
    previous: InquiryStatus


def change_status(
    db: Session,
    inquiry_id: int,
    raw_status: str,
    memo: str | None,
) -> StatusChange:
    try:
        target = InquiryStatus(raw_status)

    except ValueError as error:
        raise AppError(
            ErrorCode.INVALID_STATUS
        ) from error

    inquiry = get_inquiry(
        db, inquiry_id, for_update=True
    )

    previous = inquiry.status

    if target not in ALLOWED_TRANSITIONS.get(
        previous, set()
    ):
        raise AppError(
            ErrorCode.INVALID_STATUS_TRANSITION,
            f"{previous.value}에서 "
            f"{target.value}(으)로 변경할 수 없습니다.",
        )

    inquiry.status = target

    if memo is not None and memo.strip():
        inquiry.admin_memo = memo.strip()

    db.commit()
    db.refresh(inquiry)

    return StatusChange(inquiry, previous)