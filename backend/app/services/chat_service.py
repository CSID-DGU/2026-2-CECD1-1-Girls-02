"""고객 챗봇: 질문 → 기존 RAG Agent 그래프 실행 → 답변 또는 1:1 문의 안내.

AI 쪽 코드는 바꾸지 않고, 이미 있는 그래프(build_rag_agent_graph)의 최종 상태에서
결과(result)와 사용한 근거(context)를 꺼내 쓴다.
"""
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.context import ContextBuildResult
from app.ai.guardrails import evaluate_input_guardrail
from app.ai.models import DraftAction, DraftResult, EvidenceKind, GenerationStatus
from app.core.errors import AppError, ErrorCode
from app.db.models import (
    AiGenerationLog,
    AiGenerationSource,
    ChatConversation,
    ChatDecision,
    ChatMessage,
    ChatRole,
    GenerationPurpose,
)

logger = logging.getLogger(__name__)

HANDOFF_ANSWER = "정확한 확인이 필요한 문의예요. 1:1 문의를 남겨 주시면 담당자가 확인한 뒤 답변드릴게요."
INQUIRY_URL = "/inquiries/new"
EXCERPT_LENGTH = 200


class ChatAgent(Protocol):
    """build_rag_agent_graph()가 만든 LangGraph 그래프와 같은 모양."""

    def invoke(self, input: Mapping[str, object]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ChatEvidence:
    document_id: str
    chunk_id: str
    title: str
    excerpt: str
    cited: bool


@dataclass(frozen=True)
class ChatReply:
    conversation: ChatConversation
    answered: bool
    answer: str
    sources: list[ChatEvidence]  # 고객에게 보여줄 근거 (실제로 인용한 것만)
    handoff_reason: str | None
    request_id: str


# ---------- 대화 ----------

def find_conversation(db: Session, *, conversation_id: int | None, session_key: str) -> ChatConversation | None:
    """ID와 세션 키가 모두 맞는 대화만 돌려준다."""
    if conversation_id is None:
        return None
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is None or conversation.session_key != session_key:
        return None
    return conversation


def _start_or_continue(
    db: Session, *, brand_id: int, session_key: str, conversation_id: int | None, continuing: bool
) -> ChatConversation:
    if not continuing:
        conversation = ChatConversation(brand_id=brand_id, session_key=session_key)
        db.add(conversation)
        db.flush()
        return conversation
    conversation = find_conversation(db, conversation_id=conversation_id, session_key=session_key)
    if conversation is None or conversation.brand_id != brand_id:
        raise AppError(ErrorCode.INVALID_INPUT, "잘못된 conversationId입니다.")
    return conversation


# ---------- 결과 해석 ----------

def _evidence_of(state: Mapping[str, Any], result: DraftResult) -> list[ChatEvidence]:
    context = state.get("context")
    if not isinstance(context, ContextBuildResult):
        return []
    cited = set(result.cited_source_ids)
    return [
        ChatEvidence(
            document_id=evidence.source_id,
            chunk_id=chunk_id,
            title=evidence.title,
            excerpt=evidence.excerpt[:EXCERPT_LENGTH],
            cited=evidence.source_id in cited,
        )
        for evidence, chunk_id in zip(context.official_evidence, context.selected_chunk_ids)
    ]


def handoff_reason_code(question: str, result: DraftResult, evidence: list[ChatEvidence]) -> str:
    """명세 예시(INSUFFICIENT_EVIDENCE, SAFETY_ISSUE)와 같은 형태의 이관 사유 코드."""
    guardrail = evaluate_input_guardrail(question)
    if guardrail.should_handoff and guardrail.reason_code:
        return guardrail.reason_code  # PROMPT_INJECTION, ACCOUNT_VERIFICATION, INDIVIDUAL_ORDER, ...
    if result.event.status is GenerationStatus.INVALID_MODEL_OUTPUT:
        return "AI_OUTPUT_REJECTED"
    if result.event.status is GenerationStatus.RULE_ESCALATED and evidence:
        return "SAFETY_ISSUE"  # 근거는 있었지만 안전·긴급 규칙으로 이관
    return "INSUFFICIENT_EVIDENCE"


# ---------- 질문 처리 ----------

def ask(
    db: Session,
    *,
    brand_id: int,
    session_key: str,
    conversation_id: int | None,
    continuing: bool,
    message: str,
    agent: ChatAgent,
) -> ChatReply:
    request_id = f"req_{uuid.uuid4().hex[:12]}"

    # 1) 질문을 먼저 저장한다. AI가 실패해도 대화 이력에는 질문이 남는다.
    conversation = _start_or_continue(
        db, brand_id=brand_id, session_key=session_key, conversation_id=conversation_id, continuing=continuing
    )
    db.add(ChatMessage(conversation_id=conversation.id, role=ChatRole.USER, content=message))
    db.commit()

    # 2) AI 실행 (Chroma·Ollama가 수 초 걸릴 수 있어 DB 트랜잭션 밖에서 실행)
    state = agent.invoke({"inquiry_text": message})
    result = state.get("result")
    if not isinstance(result, DraftResult):
        raise RuntimeError("RAG Agent completed without a DraftResult")
    evidence = _evidence_of(state, result)
    log = _new_log(request_id, result, evidence)

    # 3) 검색·모델 장애는 오류로 응답한다. 실행 기록은 지표 계산을 위해 남긴다.
    if state.get("retrieval_failed"):
        _save_log_only(db, log)
        raise AppError(ErrorCode.RAG_SEARCH_FAILED)
    if result.event.status is GenerationStatus.MODEL_ERROR:
        _save_log_only(db, log)
        raise AppError(ErrorCode.LLM_UNAVAILABLE)

    answered = result.action is DraftAction.DRAFT_FOR_REVIEW and bool(result.draft_text)
    answer = result.draft_text if answered else HANDOFF_ANSWER
    reason = None if answered else handoff_reason_code(message, result, evidence)

    # 4) 답변 저장
    reply_message = ChatMessage(
        conversation_id=conversation.id,
        role=ChatRole.ASSISTANT,
        content=answer,
        decision=ChatDecision.ANSWER if answered else ChatDecision.HANDOFF,
        handoff_reason=reason,
    )
    db.add(reply_message)
    db.flush()
    log.chat_message_id = reply_message.id
    db.add(log)
    db.commit()

    return ChatReply(
        conversation=conversation,
        answered=answered,
        answer=answer,
        sources=[e for e in evidence if e.cited] if answered else [],
        handoff_reason=reason,
        request_id=request_id,
    )


def _new_log(request_id: str, result: DraftResult, evidence: list[ChatEvidence]) -> AiGenerationLog:
    log = AiGenerationLog(
        request_id=request_id,
        purpose=GenerationPurpose.CHAT_ANSWER,
        model=result.event.model,
        prompt_version=result.event.prompt_version,
        status=result.event.status,
        action=result.action,
        latency_ms=result.event.latency_ms,
    )
    log.sources = [
        AiGenerationSource(
            source_id=e.chunk_id,
            document_id=e.document_id,
            title=e.title,
            excerpt=e.excerpt,
            kind=EvidenceKind.OFFICIAL,
            cited=e.cited,
        )
        for e in evidence
    ]
    return log


def _save_log_only(db: Session, log: AiGenerationLog) -> None:
    db.add(log)
    db.commit()


# ---------- 대화 이력 ----------

@dataclass(frozen=True)
class HistoryPage:
    conversation: ChatConversation
    messages: list[ChatMessage]
    sources_by_message: dict[int, list[AiGenerationSource]]
    next_cursor: int | None  # 더 오래된 메시지가 있으면 이번 페이지에서 가장 오래된 메시지 ID


def list_messages(
    db: Session, *, conversation_id: int | None, session_key: str, limit: int, before: int | None
) -> HistoryPage:
    conversation = find_conversation(db, conversation_id=conversation_id, session_key=session_key)
    if conversation is None:
        raise AppError(ErrorCode.CONVERSATION_NOT_FOUND)

    stmt = select(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
    if before is not None:
        stmt = stmt.where(ChatMessage.id < before)
    newest_first = list(db.scalars(stmt.order_by(ChatMessage.id.desc()).limit(limit + 1)))
    has_more = len(newest_first) > limit
    messages = list(reversed(newest_first[:limit]))  # 화면에는 오래된 순서로

    assistant_ids = [m.id for m in messages if m.role is ChatRole.ASSISTANT]
    sources_by_message: dict[int, list[AiGenerationSource]] = {}
    if assistant_ids:
        logs = db.scalars(
            select(AiGenerationLog)
            .options(selectinload(AiGenerationLog.sources))
            .where(AiGenerationLog.chat_message_id.in_(assistant_ids))
        )
        for log in logs:
            sources_by_message[log.chat_message_id] = [s for s in log.sources if s.cited]

    return HistoryPage(
        conversation=conversation,
        messages=messages,
        sources_by_message=sources_by_message,
        next_cursor=messages[0].id if has_more and messages else None,
    )
