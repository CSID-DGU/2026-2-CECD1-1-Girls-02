from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EvidenceKind(StrEnum):
    OFFICIAL = "OFFICIAL"
    VOC_REFERENCE = "VOC_REFERENCE"


class DraftAction(StrEnum):
    DRAFT_FOR_REVIEW = "DRAFT_FOR_REVIEW"
    ESCALATE = "ESCALATE"


class GenerationStatus(StrEnum):
    COMPLETED = "COMPLETED"
    RULE_ESCALATED = "RULE_ESCALATED"
    MODEL_ERROR = "MODEL_ERROR"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"


@dataclass(frozen=True)
class Evidence:
    source_id: str
    title: str
    excerpt: str
    kind: EvidenceKind


@dataclass(frozen=True)
class DraftRequest:
    inquiry_text: str
    official_evidence: list[Evidence] = field(default_factory=list)
    voc_references: list[Evidence] = field(default_factory=list)
    has_individual_order_context: bool = False
    is_sensitive: bool = False
    is_safety_related: bool = False
    is_urgent: bool = False


@dataclass(frozen=True)
class GenerationEvent:
    model: str
    prompt_version: str
    official_source_ids: list[str]
    voc_reference_ids: list[str]
    latency_ms: int
    status: GenerationStatus


@dataclass(frozen=True)
class DraftResult:
    action: DraftAction
    draft_text: str | None
    escalation_reason: str | None
    cited_source_ids: list[str]
    event: GenerationEvent

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
