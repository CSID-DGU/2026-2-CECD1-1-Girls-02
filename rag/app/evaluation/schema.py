"""Ground truth uses stable IDs only; document text never belongs in evaluation data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from rag.app.retrieval.contracts import KnowledgeScope


@dataclass(frozen=True, slots=True)
class GroundTruthCase:
    case_id: str
    query: str
    scope: KnowledgeScope
    relevant_document_ids: frozenset[str]
    metadata: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GroundTruthCase":
        forbidden = {"document_text", "chunk_text", "customer_name", "email", "phone"} & value.keys()
        if forbidden:
            raise ValueError(f"GT must not contain source or personal data: {sorted(forbidden)}")
        required = {"case_id", "query", "scope", "relevant_document_ids"}
        missing = required - value.keys()
        if missing:
            raise ValueError(f"GT case missing: {sorted(missing)}")
        relevant = frozenset(map(str, value["relevant_document_ids"]))
        return cls(str(value["case_id"]), str(value["query"]), KnowledgeScope(value["scope"]), relevant, dict(value.get("metadata", {})))
