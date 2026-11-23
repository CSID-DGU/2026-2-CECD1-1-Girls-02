"""Implementation-neutral retrieval contracts and dense baseline adapters."""

from .official import (
    ChromaConnectionError,
    OfficialCollectionNotFoundError,
    OfficialKnowledgeSearchService,
    OfficialSearchConfigurationError,
    OfficialSearchError,
    OfficialSearchExecutionError,
    OfficialSearchSettings,
)

__all__ = [
    "ChromaConnectionError",
    "OfficialCollectionNotFoundError",
    "OfficialKnowledgeSearchService",
    "OfficialSearchConfigurationError",
    "OfficialSearchError",
    "OfficialSearchExecutionError",
    "OfficialSearchSettings",
]
