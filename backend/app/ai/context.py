"""Turn retrieval hits into an authoritative, bounded LLM context."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.ai.models import Evidence, EvidenceKind


@dataclass(frozen=True)
class RetrievedChunk:
    """Search-engine-neutral result passed from the retrieval module."""

    chunk_id: str
    text: str
    score: float
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class ContextBuildResult:
    official_evidence: list[Evidence]
    selected_chunk_ids: list[str]
    skipped_chunk_ids: list[str]


def _is_authoritative(metadata: Mapping[str, object]) -> bool:
    """Apply the same policy gates at query time as at ingestion time."""
    return (
        metadata.get("knowledge_scope") == "official"
        and metadata.get("is_active") is True
        and metadata.get("review_status") == "APPROVED"
        and metadata.get("allowed_use") == "DRAFT_ONLY"
    )


def build_official_context(
    hits: Iterable[RetrievedChunk], *, max_chunks: int = 5, max_characters: int = 6_000
) -> ContextBuildResult:
    """Select only approved official chunks without exceeding the prompt budget."""
    if max_chunks <= 0 or max_characters <= 0:
        raise ValueError("max_chunks and max_characters must be positive")
    evidence: list[Evidence] = []
    selected: list[str] = []
    skipped: list[str] = []
    used_characters = 0
    for hit in hits:
        metadata = hit.metadata
        source_id = metadata.get("source_id")
        title = metadata.get("title")
        if (
            not _is_authoritative(metadata)
            or not isinstance(source_id, str)
            or not source_id.strip()
            or not isinstance(title, str)
            or not title.strip()
            or not hit.text.strip()
        ):
            skipped.append(hit.chunk_id)
            continue
        if len(evidence) >= max_chunks or used_characters + len(hit.text) > max_characters:
            skipped.append(hit.chunk_id)
            continue
        evidence.append(Evidence(source_id.strip(), title.strip(), hit.text.strip(), EvidenceKind.OFFICIAL))
        selected.append(hit.chunk_id)
        used_characters += len(hit.text)
    return ContextBuildResult(evidence, selected, skipped)
