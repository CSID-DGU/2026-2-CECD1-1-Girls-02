"""고객 1:1 문의 등록·조회와 AI 초안 생성 연결."""

import logging
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.ai.models import DraftAction
from app.core.errors import AppError, ErrorCode
from app.db.models import (
    AnswerDraft,
    Inquiry,
    InquiryCategory,
    InquiryStatus,
    InquiryType,
)
from app.services.inquiry_category_service import (
    INQUIRY_TYPE_NAMES,
    get_category_tree,
)

logger = logging.getLogger(__name__)


STATUS_LABELS: dict[InquiryStatus, str] = {
    InquiryStatus.DRAFT_GENERATING: "접수 완료",
    InquiryStatus.PENDING_REVIEW: "답변 준비 중",
    InquiryStatus.IN_REVIEW: "답변 준비 중",
    InquiryStatus.ANSWERED: "답변 완료",
    InquiryStatus.CLOSED: "처리 종료",
}

AI_FAILURE_REASON = (
    "AI 초안 생성에 실패해 담당자 검토로 전환되었습니다."
)


@dataclass(frozen=True)
class NewInquiry:
    brand_id: int
    category_path: list[str] | None
    title: str
    content: str
    customer_name: str
    store_name: str | None


# ---------- 분류 경로 해석 ----------

def classify(
    db: Session,
    *,
    brand_id: int,
    category_path: list[str] | None,
) -> tuple[InquiryType, InquiryCategory | None]:
    """문의 유형과 가장 구체적인 카테고리를 찾는다."""

    names = [
        name.strip()
        for name in category_path or []
        if name and name.strip()
    ]

    type_by_name = {
        name: inquiry_type
        for inquiry_type, name in INQUIRY_TYPE_NAMES.items()
    }

    inquiry_type = InquiryType.QUESTION

    if names and names[0] in type_by_name:
        inquiry_type = type_by_name[names.pop(0)]

    if not names:
        return inquiry_type, None

    candidates: list[InquiryCategory] = []
    stack = list(get_category_tree(db, brand_id=brand_id))

    while stack:
        node = stack.pop()
        candidates.append(node.category)
        stack.extend(node.children)

    for name in reversed(names):
        matches = [
            c for c in candidates
            if c.name == name
        ]

        if matches:
            return inquiry_type, max(
                matches,
                key=lambda c: (c.depth, -c.id),
            )

    return inquiry_type, None


# ---------- 문의 등록 ----------

def create_inquiry(
    db: Session,
    new: NewInquiry,
) -> Inquiry:
    """문의 원문을 먼저 저장하고 AI 처리는 별도로 실행한다."""

    try:
        inquiry_type, category = classify(
            db,
            brand_id=new.brand_id,
            category_path=new.category_path,
        )

        inquiry = Inquiry(
            brand_id=new.brand_id,
            category_path=new.category_path,
            category_id=category.id if category else None,
            inquiry_type=inquiry_type,
            title=new.title,
            content=new.content,
            store_name=new.store_name,
            customer_name=new.customer_name,
            privacy_consented_at=datetime.now(timezone.utc),
            receipt_token=str(uuid.uuid4()),
            status=InquiryStatus.DRAFT_GENERATING,
        )

        db.add(inquiry)
        db.commit()

    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Failed to save inquiry")
        raise AppError(
            ErrorCode.INQUIRY_SAVE_FAILED
        ) from error

    db.refresh(inquiry)
    return inquiry


# ---------- 고객 조회 ----------

def get_inquiry_for_customer(
    db: Session,
    *,
    inquiry_id: int | None,
    receipt_token: str | None,
) -> Inquiry:
    if not receipt_token:
        raise AppError(ErrorCode.MISSING_RECEIPT_TOKEN)

    inquiry = (
        db.get(Inquiry, inquiry_id)
        if inquiry_id is not None
        else None
    )

    if inquiry is None:
        raise AppError(ErrorCode.INQUIRY_NOT_FOUND)

    if not secrets.compare_digest(
        inquiry.receipt_token.encode("utf-8"),
        receipt_token.encode("utf-8"),
    ):
        raise AppError(ErrorCode.INVALID_RECEIPT_TOKEN)

    return inquiry


def final_answer_of(inquiry: Inquiry) -> str | None:
    """고객에게는 승인된 최종 답변만 보여준다."""

    if inquiry.status in (
        InquiryStatus.ANSWERED,
        InquiryStatus.CLOSED,
    ):
        return inquiry.answer_content

    return None


# ---------- AI 초안 생성 ----------

def fallback_to_manual_review(
    db: Session,
    inquiry_id: int,
    reason: str = AI_FAILURE_REASON,
) -> None:
    """AI 처리 실패 시 담당자 검토 상태로 전환한다."""

    inquiry = db.scalar(
        select(Inquiry)
        .where(Inquiry.id == inquiry_id)
        .with_for_update()
    )

    if (
        inquiry is None
        or inquiry.status is not InquiryStatus.DRAFT_GENERATING
    ):
        return

    if inquiry.draft is None:
        db.add(
            AnswerDraft(
                inquiry_id=inquiry.id,
                action=DraftAction.ESCALATE,
                escalation_reason=reason,
            )
        )

    inquiry.status = InquiryStatus.PENDING_REVIEW
    db.commit()


def _default_service_factory(session: Session):
    from app.ai.service import InquiryAiService

    return InquiryAiService.from_runtime(session)


def run_ai_draft(
    inquiry_id: int,
    *,
    session_factory: Callable[[], Session] | None = None,
    service_factory: Callable[
        [Session], object
    ] = _default_service_factory,
) -> None:
    """문의 등록 응답 이후 AI 초안 생성을 실행한다."""

    from app.ai.service import InquiryAiCommand
    from app.db.session import get_session_factory

    factory = session_factory or get_session_factory()

    try:
        with factory() as session:
            try:
                service_factory(session).generate_draft(
                    InquiryAiCommand(inquiry_id=inquiry_id)
                )

            except AppError as error:
                session.rollback()

                if error.error_code in (
                    ErrorCode.CONFLICT,
                    ErrorCode.NOT_FOUND,
                ):
                    logger.info(
                        "AI draft skipped for inquiry %s",
                        inquiry_id,
                    )
                    return

                logger.exception(
                    "AI draft failed for inquiry %s",
                    inquiry_id,
                )
                fallback_to_manual_review(session, inquiry_id)

            except Exception:
                logger.exception(
                    "AI draft failed for inquiry %s",
                    inquiry_id,
                )
                session.rollback()
                fallback_to_manual_review(session, inquiry_id)

    except Exception:
        logger.exception(
            "AI background task failed for inquiry %s",
            inquiry_id,
        )


def session_factory_for(
    db: Session,
) -> Callable[[], Session]:
    """테스트에서 같은 DB에 새로운 세션을 열 때 사용한다."""

    return sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False,
    )