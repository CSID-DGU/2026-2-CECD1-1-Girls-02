from __future__ import annotations

from typing import Any

from .contracts import KnowledgeScope, SearchFilter


def chroma_where(filters: SearchFilter) -> dict[str, Any]:
    """Translate an allow-listed filter into Chroma's metadata expression format."""
    clauses: list[dict[str, Any]] = [{"knowledge_scope": filters.scope.value}]
    if filters.active_only:
        clauses.append({"is_active": True})
    if filters.scope is KnowledgeScope.OFFICIAL:
        clauses.extend(({"review_status": "APPROVED"}, {"allowed_use": "DRAFT_ONLY"}))
    if filters.document_types:
        clauses.append({"document_type": {"$in": list(filters.document_types)}})
    if filters.locales:
        clauses.append({"locale": {"$in": list(filters.locales)}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}
