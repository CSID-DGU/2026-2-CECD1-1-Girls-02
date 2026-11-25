"""Internal API boundary for creating a reviewable AI inquiry draft."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.models import DraftAction
from app.ai.service import InquiryAiCommand, InquiryAiService
from app.core.response import ApiResponse, ok
from app.db.session import get_db


router = APIRouter(prefix="/inquiries", tags=["AI"])


class InquiryDraftData(BaseModel):
    inquiry_id: int
    action: DraftAction
    draft_text: str | None
    escalation_reason: str | None
    cited_source_ids: list[str]
    generation_status: str
    latency_ms: int


DbSession = Annotated[Session, Depends(get_db)]


def get_inquiry_ai_service(db: DbSession) -> InquiryAiService:
    return InquiryAiService.from_runtime(db)


InquiryAiServiceDependency = Annotated[InquiryAiService, Depends(get_inquiry_ai_service)]


@router.post("/{inquiry_id}/ai-draft", response_model=ApiResponse[InquiryDraftData])
def create_inquiry_ai_draft(
    inquiry_id: int, service: InquiryAiServiceDependency
) -> ApiResponse[InquiryDraftData]:
    """Create one draft or handoff record for a stored inquiry.

    This endpoint intentionally accepts no raw inquiry text or safety flags.
    The service reads the stored inquiry and derives deterministic handoff
    signals on the server side.
    """
    result = service.generate_draft(InquiryAiCommand(inquiry_id=inquiry_id))
    data = InquiryDraftData(
        inquiry_id=inquiry_id,
        action=result.action,
        draft_text=result.draft_text,
        escalation_reason=result.escalation_reason,
        cited_source_ids=result.cited_source_ids,
        generation_status=result.event.status,
        latency_ms=result.event.latency_ms,
    )
    if result.action is DraftAction.ESCALATE:
        return ok(data, code="AI_HANDOFF_REQUIRED", message="담당자 검토가 필요한 문의입니다.")
    return ok(data, code="AI_DRAFT_CREATED", message="AI 답변 초안이 생성되었습니다.")
