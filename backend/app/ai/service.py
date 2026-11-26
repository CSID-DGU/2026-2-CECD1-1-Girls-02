"""Persist one AI inquiry-processing result as a short database transaction."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.handoff import requires_individual_order_handoff
from app.ai.models import DraftResult, EvidenceKind
from app.ai.runtime import get_rag_agent_runtime
from app.core.errors import AppError, ErrorCode
from app.db.models import (
    AiGenerationLog,
    AiGenerationSource,
    AnswerDraft,
    GenerationPurpose,
    Inquiry,
    InquiryStatus,
)
from app.ai.privacy import redact_pii


class AgentGraph(Protocol):
    def invoke(self, input: Mapping[str, object]) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class InquiryAiCommand:
    """Backend-derived routing information for one stored inquiry."""

    inquiry_id: int
    has_individual_order_context: bool = False
    is_sensitive: bool = False
    is_safety_related: bool = False
    is_urgent: bool = False


class InquiryAiService:
    """Invoke the RAG Agent without holding a DB transaction during AI work."""

    def __init__(self, session: Session, graph: AgentGraph) -> None:
        self._session = session
        self._graph = graph

    @classmethod
    def from_runtime(cls, session: Session) -> "InquiryAiService":
        return cls(session, get_rag_agent_runtime().graph)

    def generate_draft(self, command: InquiryAiCommand) -> DraftResult:
        inquiry_text = self._load_inquiry_text(command.inquiry_id)
        has_individual_order_context = (
            command.has_individual_order_context
            or requires_individual_order_handoff(inquiry_text)
        )

        # Chroma and Ollama may take seconds.  Do not hold a DB transaction here.
        state = self._graph.invoke(
            {
                "inquiry_text": inquiry_text,
                "has_individual_order_context": has_individual_order_context,
                "is_sensitive": command.is_sensitive,
                "is_safety_related": command.is_safety_related,
                "is_urgent": command.is_urgent,
            }
        )
        result = state.get("result")
        if not isinstance(result, DraftResult):
            raise RuntimeError("RAG Agent completed without a DraftResult")

        self._persist_result(command.inquiry_id, result)
        return result

    def _load_inquiry_text(self, inquiry_id: int) -> str:
        with self._session.begin():
            inquiry = self._session.get(Inquiry, inquiry_id)
            if inquiry is None:
                raise AppError(ErrorCode.NOT_FOUND, "문의를 찾을 수 없습니다.")
            if inquiry.status is not InquiryStatus.DRAFT_GENERATING:
                raise AppError(ErrorCode.CONFLICT, "이미 AI 처리되었거나 처리할 수 없는 문의입니다.")

            # Deliberately exclude customer_name from AI input, and mask direct identifiers.
            return redact_pii(
                f"제목: {inquiry.title}\n내용: {inquiry.content}"
            )           

    def _persist_result(self, inquiry_id: int, result: DraftResult) -> None:
        with self._session.begin():
            # Re-check under a row lock: a concurrent request must not overwrite a result.
            inquiry = self._session.get(Inquiry, inquiry_id, with_for_update=True)
            if inquiry is None:
                raise AppError(ErrorCode.NOT_FOUND, "문의를 찾을 수 없습니다.")
            if inquiry.status is not InquiryStatus.DRAFT_GENERATING:
                raise AppError(ErrorCode.CONFLICT, "이미 AI 처리된 문의입니다.")

            draft = AnswerDraft(
                inquiry_id=inquiry.id,
                action=result.action,
                ai_draft_text=result.draft_text,
                escalation_reason=result.escalation_reason,
            )
            generation = AiGenerationLog(
                purpose=GenerationPurpose.INQUIRY_DRAFT,
                inquiry_id=inquiry.id,
                model=result.event.model,
                prompt_version=result.event.prompt_version,
                status=result.event.status,
                action=result.action,
                latency_ms=result.event.latency_ms,
            )
            generation.sources = self._sources_from(result)

            inquiry.status = InquiryStatus.PENDING_REVIEW
            self._session.add_all((draft, generation))

    @staticmethod
    def _sources_from(result: DraftResult) -> list[AiGenerationSource]:
        cited = set(result.cited_source_ids)
        sources: list[AiGenerationSource] = []
        seen: set[tuple[str, EvidenceKind]] = set()
        for source_id, kind in (
            *((source_id, EvidenceKind.OFFICIAL) for source_id in result.event.official_source_ids),
            *((source_id, EvidenceKind.VOC_REFERENCE) for source_id in result.event.voc_reference_ids),
        ):
            key = (source_id, kind)
            if key not in seen:
                seen.add(key)
                sources.append(
                    AiGenerationSource(
                        source_id=source_id,
                        kind=kind,
                        cited=source_id in cited,
                    )
                )
        return sources
