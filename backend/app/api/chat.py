import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query

from app.api.deps import DbSession
from app.core.errors import AppError, ErrorCode
from app.core.exception_handlers import field_error_codes
from app.core.public_id import CONVERSATION, MESSAGE, parse_public_id
from app.core.response import ApiResponse, ok
from app.schemas.chat import ChatHistoryData, ChatMessageRequest, ChatReplyData
from app.services import chat_service
from app.services.brand_service import get_active_brand

router = APIRouter(prefix="/api/v1/chat", tags=["챗봇 (고객)"])

SESSION_HEADER = ("header", "X-Chat-Session-Key")
SessionKey = Annotated[str, Header(alias="X-Chat-Session-Key", description="브라우저에 저장한 챗봇 세션 키 (UUID)")]


def get_chat_agent() -> chat_service.ChatAgent:
    """실제 RAG Agent 그래프. 테스트에서 가짜로 바꿔 끼운다."""
    from app.ai.retrieval_adapter import OfficialRetrievalUnavailable
    from app.ai.runtime import get_rag_agent_runtime

    try:
        return get_rag_agent_runtime().graph
    except OfficialRetrievalUnavailable as error:
        raise AppError(ErrorCode.RAG_SEARCH_FAILED) from error


def _valid_session_key(raw: str, error: ErrorCode) -> str:
    try:
        return str(uuid.UUID(raw))
    except ValueError as exc:
        raise AppError(error, "X-Chat-Session-Key는 UUID 형식이어야 합니다.") from exc


@router.post("/messages", response_model=ApiResponse[ChatReplyData])
@field_error_codes({SESSION_HEADER: ErrorCode.MISSING_PARAMETER})
def send_message(
    body: ChatMessageRequest,
    db: DbSession,
    session_key: SessionKey,
    agent: Annotated[chat_service.ChatAgent, Depends(get_chat_agent)],
) -> ApiResponse[ChatReplyData]:
    brand = get_active_brand(db, body.brand_id)
    continuing = body.conversation_id is not None
    reply = chat_service.ask(
        db,
        brand_id=brand.id,
        session_key=_valid_session_key(session_key, ErrorCode.INVALID_INPUT),
        conversation_id=parse_public_id(CONVERSATION, body.conversation_id) if continuing else None,
        continuing=continuing,
        message=body.message,
        agent=agent,
    )
    return ok(ChatReplyData.from_reply(reply), code="CHAT_MESSAGE_SUCCESS", message="챗봇 응답을 생성했습니다.")


@router.get("/conversations/{conversationId}/messages", response_model=ApiResponse[ChatHistoryData])
@field_error_codes({SESSION_HEADER: ErrorCode.MISSING_PARAMETER})
def get_messages(
    db: DbSession,
    session_key: SessionKey,
    conversation_id: Annotated[str, Path(alias="conversationId", description="대화 ID (예: conv_001)")],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[str | None, Query(description="이전 메시지 조회용 커서 (이전 응답의 nextCursor)")] = None,
) -> ApiResponse[ChatHistoryData]:
    before_id = parse_public_id(MESSAGE, before) if before else None
    if before and before_id is None:
        raise AppError(ErrorCode.INVALID_PARAMETER, "before 커서 형식이 올바르지 않습니다.")
    page = chat_service.list_messages(
        db,
        conversation_id=parse_public_id(CONVERSATION, conversation_id),
        session_key=_valid_session_key(session_key, ErrorCode.CONVERSATION_NOT_FOUND),
        limit=limit,
        before=before_id,
    )
    return ok(
        ChatHistoryData.from_page(page),
        code="GET_CHAT_MESSAGES_SUCCESS",
        message="챗봇 대화 이력 조회에 성공했습니다.",
    )
